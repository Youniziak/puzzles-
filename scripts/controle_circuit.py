"""Chaîne puzzle, étape 0 quater — contrôle du circuit, en quelques secondes, avant tout routage et sans KiCad.
Il attrape les erreurs « bêtes » que le contrôle électrique de KiCad ne voit pas, en lisant le nom de chaque broche,
son type (types-broches.json, sinon l'export EasyGerber), sa liaison et sa position :
  1. une broche de masse (GND, VSS, PGND, AGND, RFGND…) qui n'est pas sur la masse ;                         ✗
  2. une broche d'alimentation (VDD, VCC, VIN, VBUS, PVDD, 3V3…) branchée sur la masse ;                      ✗
  3. SDA et SCL inversés (une broche SDA ou SDIO sur une liaison SCL, ou l'inverse) ;                         ✗
  4. VIN et VOUT d'un régulateur dans le mauvais sens (tension lue dans le nom des liaisons : 5V, VBUS, 3V3) ;   ✗
  5. gauche et droite inversées (une broche INL ou OUTL sur une liaison du côté droit, ou l'inverse) ;         ⚠
  6. une broche NC reliée à d'autres broches ;                                                                 ⚠
  7. une entrée (type « input ») reliée à rien ;                                                               ⚠
  8. une alimentation de puce sans condensateur vers la masse, ou avec le plus proche à plus de 5 mm ;        ⚠
  9. un bus I2C (liaison SDA ou SCL) sans résistance de tirage vers une alimentation.                         ⚠
 10. plus de 10 µF de condensateurs sur le VBUS d'une prise USB (règle de l'USB 2.0 : au plus 50 µC pris
     au branchement, soit 10 µF sous 5 V ; d'après une note de Nuvoton qui reprend l'USB-IF) ;                ⚠
 11. une ligne de données USB (D+, D-) qui va de la prise à une puce sans résistance en série : certains
     fabricants recommandent d'en prévoir la place (Espressif pour l'ESP32-S3 : 22 ou 33 Ω).                ⚠
Les règles 10 et 11 viennent des contrôles de l'outil kicad-happy, refaits à la main le 24/10/2026 sur la radio v4.
Une alerte vérifiée par une personne (erreur du catalogue, choix voulu) se note dans bibliotheque/controles-verifies.json,
avec la raison, qui et quand : elle n'est plus comptée, mais reste écrite dans le bilan.
Usage : python3 controle_circuit.py cartes/ma-carte.json [dossier_projet]    (code de sortie 1 s'il y a un ✗)"""
import json, math, os, re, sys
from collections import defaultdict
from description import Carte

CARTE = Carte(sys.argv[1])
M = CARTE.masse
DIST_DECOUPLAGE = 5.0
f_types = os.path.join(CARTE.empreintes, 'types-broches.json')
TYPES = json.load(open(f_types, encoding='utf-8'))['pieces'] if os.path.exists(f_types) else {}
f_verif = os.path.join(CARTE.bibliotheque, 'controles-verifies.json')
VERIFIES = json.load(open(f_verif, encoding='utf-8')).get('verifies', []) if os.path.exists(f_verif) else []

MASSE = re.compile(r'^(P|A|D|RF|S|E)?(GND|VSS)\d*$')
ALIM = re.compile(r'^(P|A|D)?(VDD|VCC|VIN|VBUS|VBAT|VIO|VI|3V3|5V)\d*$')
PASSIF = re.compile(r'^(C|R|L|FB)\d')

broches = []
for b in CARTE.blocs:
    for p in b.design['parts']:
        ty = TYPES.get(p.get('lcscPartNumber'), {}).get('broches', {})
        for q in p['pads']:
            num = str(q.get('id'))
            broches.append(dict(bloc=b.id, ref=CARTE.repere(b, p['id']), num=num, lcsc=p.get('lcscPartNumber'), mpn=p.get('mpn', ''),
                                genre=p.get('type'), valeur=p.get('value'), desc=p.get('description') or '',
                                nom=(q.get('signalName') or '').strip().upper(), eg=q.get('electricalType'),
                                type=ty.get(num, {}).get('type'), net=CARTE.reseau(b, q.get('netName')), xy=b.pastille(p, q)))
par_net = defaultdict(list)
par_ref = defaultdict(list)
for x in broches:
    par_ref[x['ref']].append(x)
    if x['net']:
        par_net[x['net']].append(x)

alertes = []       # (signe, règle, broche ou None, texte)


def alerte(signe, regle, x, texte):
    alertes.append((signe, regle, x, texte))


def nom_broche(x):
    return f"{x['ref']}.{x['num']} « {x['nom'] or '?'} » ({x['mpn']})"


def tension(net):
    """Tension lue dans le nom d'une liaison : 3V3 → 3,3 ; 5V, VBUS → 5 ; sinon None."""
    if not net:
        return None
    u = net.upper()
    if 'VBUS' in u:
        return 5.0
    m = re.search(r'(\d+)V(\d+)?', u)
    return float(f"{m.group(1)}.{m.group(2) or 0}") if m else None


def cote(nom):
    """Côté gauche (G) ou droit (D) lu dans un nom de broche ou de liaison ; None si rien de sûr."""
    u = nom.upper()
    g = re.search(r'(^|[^A-Z])(L|LEFT)([^A-Z]|$)|LOUT|OUTL|INL', u)
    d = re.search(r'(^|[^A-Z])(R|RIGHT)([^A-Z]|$)|ROUT|OUTR|INR', u)
    return 'G' if g and not d else 'D' if d and not g else None


def farads(valeur):
    """« 22uF », « 100nF », « 4,7 µF » → farads ; None si la valeur ne se lit pas comme une capacité."""
    m = re.match(r'^\s*(\d+(?:[.,]\d+)?)\s*([pnuµm]?)F?\b', valeur or '')
    if not m:
        return None
    return float(m.group(1).replace(',', '.')) * {'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'µ': 1e-6, 'm': 1e-3, '': 1}[m.group(2)]


def condensateurs_vers_masse(net):
    """Condensateurs dont une broche est sur « net » et l'autre sur la masse : [(ref, position de la broche)]."""
    out = []
    for y in par_net.get(net, []):
        if y['ref'][:1] == 'C' and PASSIF.match(y['ref']):
            if any(z['net'] == M for z in par_ref[y['ref']] if z['num'] != y['num']):
                out.append((y['ref'], y['xy']))
    return out


for x in broches:
    n, net = x['nom'], x['net']
    toks = set(re.split(r'[^A-Z0-9]+', n)) - {''}
    if MASSE.match(n) and net != M:
        alerte('✗', 'masse', x, f"{nom_broche(x)} : broche de masse sur la liaison {net or '(rien)'}, pas sur {M}")
    if ALIM.match(n) and net == M:
        alerte('✗', 'alimentation', x, f"{nom_broche(x)} : broche d'alimentation branchée sur la masse")
    if net and (({'SDA', 'SDIO'} & toks and 'SCL' in net.upper()) or ({'SCL', 'SCLK'} & toks and 'SDA' in net.upper())):
        alerte('✗', 'i2c', x, f"{nom_broche(x)} : sur la liaison {net} : SDA et SCL inversés ?")
    if net and cote(n) and cote(net) and cote(n) != cote(net):
        alerte('⚠', 'gauche-droite', x, f"{nom_broche(x)} : côté {'gauche' if cote(n) == 'G' else 'droit'}, sur la liaison {net} du côté opposé")
    if (n == 'NC' or x['eg'] == 'nc' or x['type'] == 'no_connect') and net and len(par_net[net]) > 1:
        alerte('⚠', 'nc', x, f"{nom_broche(x)} : broche « non connectée » reliée à {net} ({len(par_net[net]) - 1} autre(s) broche(s))")
    if (x['type'] == 'input' or (x['type'] is None and x['eg'] == 'input')) and not net:
        alerte('⚠', 'entree', x, f"{nom_broche(x)} : entrée reliée à rien (en l'air)")

# découplage : chaque alimentation de puce (type power_in ou power_out, ou nom d'alimentation) a son condensateur vers la masse
vus = set()
for x in broches:
    if PASSIF.match(x['ref']) or not x['net'] or x['net'] == M or MASSE.match(x['nom']):
        continue
    if not (x['type'] in ('power_in', 'power_out') or ALIM.match(x['nom'])):
        continue
    if x['ref'][:1] in 'JTS' or x['ref'][:2] == 'TP':        # prises, pastilles de test, boutons : pas de découplage à eux
        continue
    cles = (x['ref'], x['net'], x['nom'])
    if cles in vus:
        continue
    vus.add(cles)
    caps = sorted((math.dist(x['xy'], xy), r) for r, xy in condensateurs_vers_masse(x['net']))
    if not caps:
        alerte('⚠', 'decouplage', x, f"{nom_broche(x)} ({x['net']}) : aucun condensateur vers la masse sur cette liaison")
    elif caps[0][0] > DIST_DECOUPLAGE:
        alerte('⚠', 'decouplage', x, f"{nom_broche(x)} ({x['net']}) : le condensateur le plus proche ({caps[0][1]}) est à "
               f"{caps[0][0]:.1f} mm (au plus {DIST_DECOUPLAGE:g} mm)".replace('.', ','))
    else:
        alerte('✓', 'decouplage', x, f"{nom_broche(x)} ({x['net']}) : {caps[0][1]} à {caps[0][0]:.1f} mm".replace('.', ','))

# I2C : une résistance de tirage vers une alimentation sur chaque liaison SDA et SCL
for net in sorted(par_net):
    noms = {y['nom'] for y in par_net[net]}
    if not (re.search(r'SDA|SCL', net.upper()) or noms & {'SDA', 'SDIO', 'SCL', 'SCLK'}):
        continue
    tirages = [(y['ref'], z['net']) for y in par_net[net] if y['ref'][:1] == 'R' and PASSIF.match(y['ref'])
               for z in par_ref[y['ref']] if z['num'] != y['num'] and z['net'] and z['net'] != M]
    if tirages:
        alerte('✓', 'tirage', None, f"{net} : {', '.join(f'{r} vers {n}' for r, n in tirages)}")
    else:
        alerte('⚠', 'tirage', None, f"{net} : bus I2C sans résistance de tirage vers une alimentation")

# USB : condensateurs sur VBUS (règle 10) et résistance en série sur les lignes de données (règle 11)
DONNEES_USB = re.compile(r'^(D[+-]|DP\d*|DN\d*)$')
vus_usb = set()
for x in broches:
    if x['genre'] != 'connector' or not x['net'] or x['net'] == M or x['net'] in vus_usb:
        continue
    if 'VBUS' in x['nom']:
        vus_usb.add(x['net'])
        caps = sorted({(r, farads(next(y['valeur'] for y in par_ref[r]))) for r, _ in condensateurs_vers_masse(x['net'])})
        total = sum(c for _, c in caps if c)
        detail = ', '.join(f"{r} {next(y['valeur'] for y in par_ref[r])}" for r, _ in caps)
        texte = f"{x['net']} (prise {x['ref']}) : {total * 1e6:.1f} µF de condensateurs ({detail})".replace('.', ',')
        if any(c is None for _, c in caps):
            texte += " ; valeur illisible pour " + ', '.join(r for r, c in caps if c is None)
        if total > 10e-6:
            alerte('⚠', 'usb-vbus', x, texte + " : l'USB 2.0 en permet 10 µF au plus (charge prise au branchement)")
        else:
            alerte('✓', 'usb-vbus', x, texte)
    elif DONNEES_USB.match(x['nom']):
        vus_usb.add(x['net'])
        for y in par_net[x['net']]:
            if y['genre'] in ('ic', 'module') and not re.search(r'ESD|TVS', y['desc'], re.I):
                alerte('⚠', 'usb-serie', y, f"{nom_broche(y)} : ligne USB {x['net']} reliée à la prise {x['ref']} sans résistance en série ; "
                       "vérifier dans le guide du fabricant de la puce s'il en faut une (Espressif, pour l'ESP32-S3 : en prévoir la place, 22 ou 33 Ω)")

# régulateurs : VIN sur la tension la plus haute
for ref, bs in sorted(par_ref.items()):
    e = next((x for x in bs if x['nom'] in ('VIN', 'VI', 'IN')), None)
    s = next((x for x in bs if x['nom'] in ('VOUT', 'VO', 'OUT')), None)
    if e and s:
        ve, vs = tension(e['net']), tension(s['net'])
        if ve is not None and vs is not None:
            if ve > vs:
                alerte('✓', 'regulateur', e, f"{ref} ({e['mpn']}) : reçoit {e['net']} ({ve:g} V), sort {s['net']} ({vs:g} V)".replace('.', ','))
            else:
                alerte('✗', 'regulateur', e, f"{ref} ({e['mpn']}) : VIN sur {e['net']} ({ve:g} V) et VOUT sur {s['net']} ({vs:g} V) : à l'envers ?".replace('.', ','))

# alertes déjà vérifiées par une personne
retenues, verifiees = [], []
for signe, regle, x, texte in alertes:
    v = next((v for v in VERIFIES if x and v.get('lcsc') == x['lcsc'] and str(v.get('broche')) == x['num'] and v.get('regle') == regle), None)
    if v and signe != '✓':
        verifiees.append((signe, texte, v))
    else:
        retenues.append((signe, texte))

lignes = [f"CONTRÔLE DU CIRCUIT — {CARTE.nom}", f"{len(broches)} broches, {len(par_net)} liaisons"
          + ('' if TYPES else " ; types-broches.json absent : seuls les noms et l'export EasyGerber servent"), '']
for signe in ('✗', '⚠', '✓'):
    lignes += [f"{signe} {t}" for s, t in retenues if s == signe]
if verifiees:
    lignes += ['', "Alertes déjà vérifiées (bibliotheque/controles-verifies.json) :"]
    lignes += [f"  ({s}) {t} — vérifié : {v['raison']} ({v.get('verifie_par', '?')}, {v.get('le', '?')})" for s, t, v in verifiees]
nx, nw = sum(1 for s, _ in retenues if s == '✗'), sum(1 for s, _ in retenues if s == '⚠')
lignes += ['', "Bilan : " + (f"{nx} erreur(s) à corriger avant de router" if nx else "aucune erreur")
           + (f", {nw} point(s) à regarder" if nw else '') + '.',
           "Ce contrôle ne voit pas : la tension que supporte chaque broche (il faudrait les fiches), ni si une valeur est bonne."]
print('\n'.join(lignes))
if len(sys.argv) > 2:
    os.makedirs(sys.argv[2], exist_ok=True)
    open(os.path.join(sys.argv[2], 'controle-circuit.txt'), 'w', encoding='utf-8').write('\n'.join(lignes) + '\n')
sys.exit(1 if nx else 0)
