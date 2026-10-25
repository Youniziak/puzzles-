"""Montages réels : comment d'autres ont branché une puce, d'après des schémas publiés.

Toutes les liaisons du rapport sortent de KiCad lui-même (kicad-cli), lisant le schéma d'origine ; aucune ne vient
d'une conversion faite par un jeu de données (pourquoi : outils/jeux_donnees.py). Sources, de la plus sûre à la moins
sûre (détail et licences : outils/jeux_donnees.py) :
  1. ohmatic : 1 000 schémas, chacun avec un niveau de confiance. « Vérifié » : au moins deux familles de sources
     indépendantes ; « admis d'office » : la liste de départ d'Ohmatic, sans nouvelle vérification ;
  2. kicad9plus : environ 300 schémas KiCad 9 et plus, avec la licence de chacun ;
  3. open-schematics : 88 000 schémas tirés de 30 000 dépôts GitHub, le plus large. La puce y est cherchée par le nom
     de son symbole, et par sa valeur grâce au jeu « circuits », qui ne sert que d'index.
Un même dépôt n'est pris que dans la source la plus sûre qui l'a (jusqu'à 4 de ses schémas : versions, cartes).
Chaque source ne donne qu'une feuille par schéma : ce qui passe par une autre feuille apparaît comme « réseau X, rien
d'autre sur cette feuille ».

En tête du rapport : ce qui revient chez au moins deux auteurs différents (valeurs des composants branchés sur chaque
broche ; deux dépôts d'un même compte GitHub comptent pour un, une copie exacte d'un schéma déjà vu n'est pas
recomptée). C'est la règle de la méthode : une piste est retenue quand deux sources indépendantes la donnent.
Alertes : un même signal sur d'autres broches que chez les autres (autre boîtier, module, ou symbole faux) ; une
broche de masse et une d'alimentation sur le même réseau (un court-circuit : la puce n'est pas comptée) ; une broche
de masse ou d'alimentation non reliée. Ce sont des projets publiés, pas des montages vérifiés : ils servent à
comparer et à poser de bonnes questions à un électronicien, pas à prouver qu'un montage marche. Chaque projet garde
sa propre licence : on lit et on cite, on ne recopie rien dans le dépôt (les schémas téléchargés vont dans
dossier_sortie/schemas/, que Git ignore).

Il faut internet (environ 5 minutes et 290 Mo mis en cache la première fois), KiCad (kicad-cli) et polars.
Usage : python3 outils/montages_reels.py 'SI4732' dossier_sortie/ [--sources ohmatic,kicad9plus,open-schematics]
                                                                  [--max 15]
        Le motif est une expression régulière simple, sans distinction de majuscules. Plusieurs puces :
        'SI4732|PAM8403' (chacune est cherchée à son tour, avec son propre --max)."""
import argparse, functools, hashlib, json, os, re, subprocess, sys, time
from collections import Counter, defaultdict
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jeux_donnees import JEUX, telecharger, depot_de, index_open_schematics, fichier_open_schematics

ap = argparse.ArgumentParser(description="Comment d'autres ont branché une puce, d'après des schémas publiés.")
ap.add_argument('motif')
ap.add_argument('sortie')
ap.add_argument('--sources', default='ohmatic,kicad9plus,open-schematics')
ap.add_argument('--max', type=int, default=15, help='dépôts au plus par source et par puce (15 par défaut)')
A = ap.parse_args()
MOTIF, SORTIE = A.motif, A.sortie
SCHEMAS = os.path.join(SORTIE, 'schemas')
os.makedirs(SCHEMAS, exist_ok=True)
motif_re = re.compile(MOTIF, re.I)


def alternatives(motif):
    """« SI4732|PAM8403|SY8089 » → les trois puces, cherchées chacune à son tour (« SI47(32|35) » reste entier)."""
    morceaux, prof, cour = [], 0, ''
    for c in motif:
        prof += {'(': 1, ')': -1}.get(c, 0)
        if c == '|' and prof == 0:
            morceaux.append(cour); cour = ''
        else:
            cour += c
    return [m for m in morceaux + [cour] if m]


def info(*x):
    print(*x, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- liaisons d'un schéma, par KiCad
def lire(texte):
    jetons = re.findall(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+', texte)
    pile, cour = [], []
    for j in jetons:
        if j == '(':
            pile.append(cour); cour = []
        elif j == ')':
            fini, cour = cour, pile.pop(); cour.append(fini)
        else:
            cour.append(j[1:-1] if j.startswith('"') else j)
    return cour[0]


def champ(e, nom):
    return next((x for x in e or [] if isinstance(x, list) and x and x[0] == nom), None)


def liaisons_kicad(chemin_sch):
    """(valeurs, réseaux) d'après KiCad, ou None si KiCad ne sait pas en sortir les liaisons. La valeur d'une pièce
    dont seul le symbole porte le motif devient « valeur (symbole) »."""
    net = chemin_sch + '.net'
    try:
        k = subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '--output', net, chemin_sch],
                           capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:   # un schéma que KiCad n'arrive pas à lire ne doit pas bloquer les autres
        return None
    if k.returncode or not os.path.exists(net):
        return None
    arbre = lire(open(net, encoding='utf-8', errors='replace').read())
    valeurs = {}
    for c in (champ(arbre, 'components') or [None])[1:]:
        v = (champ(c, 'value') or [None, ''])[1]
        piece = (champ(champ(c, 'libsource'), 'part') or [None, ''])[1]
        valeurs[champ(c, 'ref')[1]] = v if motif_re.search(v) or not motif_re.search(piece) else f'{v} ({piece})'
    reseaux = [(champ(n, 'name')[1], [(champ(x, 'ref')[1], champ(x, 'pin')[1], (champ(x, 'pinfunction') or [None, ''])[1])
                                       for x in n if isinstance(x, list) and x and x[0] == 'node'])
               for n in (champ(arbre, 'nets') or [None])[1:]]
    return valeurs, reseaux


def propre(f, pin):
    """Nom de broche lisible : KiCad 10 y colle « _numéro », qu'on enlève ; « ~{SHDN} » (barre au-dessus : active
    à 0) devient « /SHDN »."""
    f = re.sub(r'~\{([^}]*)\}', r'/\1', re.sub(rf'_{re.escape(pin)}$', '', f or '')).strip()
    return '' if f in ('', '~') else f


PAS_UNE_PUCE = re.compile(r'(R|C|L|D|J|JP|P|SW|S|TP|H|MH|Y|X|F|FB|LED|BT|K|Q|LS|BZ|NT|SJ)\d', re.I)


def broches_des_puces(valeurs, reseaux):
    """Broches des puces dont la valeur porte le motif (pas les cavaliers, connecteurs… qui portent son nom)."""
    res = {}
    for puce in [r for r, v in valeurs.items() if motif_re.search(v or '') and not PAS_UNE_PUCE.match(r)]:
        b = [(pin, propre(fonction, pin), list(dict.fromkeys(r2 for r2, _, _ in noeuds if r2 != puce)), nom)
             for nom, noeuds in reseaux for ref, pin, fonction in noeuds if ref == puce]
        if b:
            res[puce] = b
    return res


R_MASSE = re.compile(r'^([ADPS]?GND\w*|EARTH|0V)$', re.I)               # noms de réseau
F_MASSE = re.compile(r'^/?([ADPS]?GND|VSS)\w*$', re.I)                    # noms de broche
F_ALIM = re.compile(r'^/?([ADP]?V(DD|CC)|VIN|VBAT|VBUS)\w*$', re.I)


def court(nom):
    return (nom or '').split('/')[-1]


def masse(nom):
    return bool(R_MASSE.match(court(nom)))


def nomme(nom):
    """Nom donné au réseau par l'auteur ; vide pour ceux que KiCad fabrique (« Net-(U7-INL) », « unconnected-(…) »)."""
    return '' if re.search(r'(^|/)(Net|unconnected)-\(', nom or '') else re.sub(r'~\{([^}]*)\}', r'/\1', court(nom))


def masse_et_alim(b):
    """Vrai si une broche de masse et une broche d'alimentation de la puce sont sur le même réseau : un court-circuit,
    donc une erreur du schéma d'origine ou une lecture ratée."""
    par_reseau = defaultdict(set)
    for pin, fonction, autres, nom in b:
        par_reseau[nom].add('m' if F_MASSE.match(fonction) else 'a' if F_ALIM.match(fonction) else '')
    return any({'m', 'a'} <= s for s in par_reseau.values())


def decrire(nom, autres, valeurs):
    if masse(nom):
        c = court(nom)
        txt = 'masse' if c.upper() == 'GND' else f'masse ({c})'
        return txt + (", seule sur ce réseau dans cette feuille : reliée ailleurs ?" if not autres else '')
    n = nomme(nom)
    if not autres:
        return f"réseau {n}, rien d'autre sur cette feuille" if n else 'non reliée'
    if len(autres) > 12:
        return f'réseau {n or "sans nom"}, partagé par {len(autres)} composants'
    txt = ', '.join(f'{r} {valeurs.get(r, "?")}' for r in autres[:6])
    txt += f' et {len(autres) - 6} autre' + 's' * (len(autres) > 7) if len(autres) > 6 else ''
    return txt + (f' (réseau {n})' if n else '')


def ordre(pin):
    return (int(pin) if pin.isdigit() else 9999, pin)


# ---------------------------------------------------------------- ce qui revient d'un projet à l'autre
MULT = {'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'm': 1e-3, '': 1.0, 'k': 1e3, 'K': 1e3, 'M': 1e6, 'R': 1.0}
UNITES = {'C': (('µF', 1e-6), ('nF', 1e-9), ('pF', 1e-12)), 'R': (('MΩ', 1e6), ('kΩ', 1e3), ('Ω', 1.0)),
          'L': (('mH', 1e-3), ('µH', 1e-6), ('nH', 1e-9))}


def valeur_lisible(v, genre):
    """« 0.1uF » → « 100 nF », « 4k7 » → « 4,7 kΩ » ; None si la valeur ne se lit pas."""
    if genre == 'Y':
        return (v or '').strip() or None
    s = (v or '').replace('µ', 'u').replace('μ', 'u').replace('Ω', '').replace(',', '.').replace(' ', '')
    s = re.sub(r'(?i)ohms?$', '', s)
    m = re.fullmatch(r'(\d+(?:\.\d+)?)([pnumkKMR]?)(\d*)[FH]?', s)
    if not m:
        return None
    ent, unite, dec = m.groups()
    x = float(ent + ('.' + dec if dec else '')) * MULT[unite]
    for nom, f in UNITES[genre]:
        if x >= f * 0.999:
            return f'{x / f:g} {nom}'.replace('.', ',')
    nom, f = UNITES[genre][-1]
    return f'{x / f:g} {nom}'.replace('.', ',')


def genre(ref):
    m = re.match(r'(C|R|L|FB|Y|X)\d', ref or '')
    return None if not m else {'FB': 'L', 'X': 'Y'}.get(m.group(1), m.group(1))


SYNTH = defaultdict(lambda: defaultdict(set))     # (puce, broche, nom de la broche) → ce qui y est branché → dépôts
COMPTES = defaultdict(set)                         # puce → dépôts comptés
BROCHAGES = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))   # puce → signal → broches → dépôts


def signal(fonction):
    """Premier nom de la broche, sans les signes d'inversion : « GPO2/[/INT] » → « GPO2 », « *RST » → « RST »."""
    s = re.sub(r'[\[\]]', '', fonction or '').lstrip('/*~').split('/')[0].upper()
    return '' if s in ('', 'NC', 'DNC', 'NC1', 'NC2') else s


def noter_brochage(famille_, depot, b):
    par_signal = defaultdict(set)
    for pin, fonction, _, _ in b:
        if signal(fonction):
            par_signal[signal(fonction)].add(pin)
    for sig, pins in par_signal.items():
        BROCHAGES[famille_][sig][tuple(sorted(pins, key=ordre))].add(depot)


def brochage_different(fam):
    """Ligne d'alerte, ou rien : un même signal sur d'autres broches que dans la plupart des projets, pour une même
    puce (même nom, même nombre de broches). Autre boîtier, autre module tout fait, ou symbole fait main avec un
    mauvais brochage : à vérifier sur la fiche technique avant de s'en inspirer."""
    ecarts = []
    for sig, variantes in sorted(BROCHAGES[fam].items()):
        v = sorted(variantes.items(), key=lambda x: -len(x[1]))
        if len(v) > 1 and len(v[0][1]) >= 2 and len(v[0][1]) > len(v[1][1]):
            ecarts.append(f'{sig} en broche {"+".join(v[0][0]) or "sans numéro"} ({len(v[0][1])} projets), mais '
                          + ' ou '.join(f'{"+".join(p) or "sans numéro"} chez {", ".join(sorted(d))}' for p, d in v[1:]))
    if not ecarts:
        return []
    return ['    attention : brochage différent selon les projets (autre boîtier, module tout fait, ou symbole faux : '
            'à vérifier sur la fiche technique) : ' + ' ; '.join(ecarts[:6])
            + (f' ; et {len(ecarts) - 6} autre(s) signal(aux)' if len(ecarts) > 6 else '')]


def famille(valeur, b):
    """« PAM8403 (16 broches) » : le nombre de broches sépare la puce nue des modules tout faits qui portent son nom."""
    return f'{motif_re.search(valeur).group(0).upper()} ({len(b)} broches)'


def auteur(depot):
    """Le compte GitHub : deux dépôts d'un même compte ne sont pas deux sources indépendantes."""
    return depot.split('/')[0]


def noter(depot, valeurs, broches):
    for puce, b in broches.items():
        famille_ = famille(valeurs[puce], b)
        COMPTES[famille_].add(depot)
        noter_brochage(famille_, depot, b)
        for pin, fonction, autres, nom in b:
            cle = (famille_, pin, fonction.upper())
            if masse(nom):
                SYNTH[cle]['à la masse'].add(auteur(depot))
            elif not autres:
                if not nomme(nom):
                    SYNTH[cle]['non reliée'].add(auteur(depot))
            elif len(autres) <= 12:   # au-delà, réseau d'alimentation partagé : on ne sait pas quel composant va avec la puce
                for r2 in autres:
                    g = genre(r2)
                    v = valeur_lisible(valeurs.get(r2, ''), g) if g else None
                    if v:
                        SYNTH[cle][v].add(auteur(depot))


# ---------------------------------------------------------------- rapport
RAPPORT, VUS, BILAN, EMPREINTES = [], set(), [], {}


def projet(depot, entete, valeurs, broches, chemin):
    """Écrit le projet dans le rapport ; faux si la puce cherchée n'est pas sur la feuille. Un schéma identique, au
    caractère près, à un schéma déjà vu (copie, fourche) est signalé et pas recompté."""
    if not broches:
        return False
    VUS.add(depot)
    empreinte = os.path.basename(chemin).rsplit('-', 1)[-1].split('.')[0]
    if empreinte in EMPREINTES:
        RAPPORT.extend([entete, f'   même schéma, au caractère près, que {EMPREINTES[empreinte]} (copie ou fourche) : '
                                'non recompté.', ''])
        return True
    EMPREINTES[empreinte] = depot
    douteux = {p for p, b in broches.items() if masse_et_alim(b)}
    noter(depot, valeurs, {p: b for p, b in broches.items() if p not in douteux})
    RAPPORT.append(entete)
    for puce, b in broches.items():
        RAPPORT.append(f'   {puce} = {valeurs[puce]} ({len(b)} broches)')
        if puce in douteux:
            RAPPORT.append("     attention : une broche de masse et une broche d'alimentation de cette puce sont sur le même "
                           "réseau (un court-circuit) : erreur dans le schéma d'origine, ou lecture ratée. Non compté.")
        flottantes = [f'{fonction} ({pin})' for pin, fonction, autres, nom in sorted(b, key=lambda x: ordre(x[0]))
                      if not autres and not nomme(nom) and (F_MASSE.match(fonction) or F_ALIM.match(fonction))]
        if flottantes:
            RAPPORT.append("     attention : broche de masse ou d'alimentation non reliée : " + ', '.join(flottantes)
                           + " (erreur dans le schéma d'origine ?)")
        for pin, fonction, autres, nom in sorted(b, key=lambda x: ordre(x[0])):
            RAPPORT.append(f'     broche {pin or "sans numéro"}{" " + fonction if fonction else ""} → {decrire(nom, autres, valeurs)}')
    RAPPORT.append('')
    return True


def sans_liaisons(entete, raison, depot):
    RAPPORT.extend([entete, '   ' + raison, ''])
    VUS.add(depot)


def copie_schema(texte_ou_chemin, depot, ext, est_chemin=False):
    data = open(texte_ou_chemin, 'rb').read() if est_chemin else texte_ou_chemin.encode('utf-8')
    f = os.path.join(SCHEMAS, f"{depot.replace('/', '__')}-{hashlib.sha1(data).hexdigest()[:10]}{ext}")
    open(f, 'wb').write(data)
    return f


# ---------------------------------------------------------------- les sources
def place(depot, avant, montres):
    """Vrai si ce dépôt peut encore être montré par cette source : pas déjà pris par une source plus sûre, au plus
    4 schémas par dépôt, au plus --max dépôts."""
    return depot not in avant and montres[depot] < 4 and (depot in montres or len(montres) < A.max)


def source_ohmatic(alt):
    J = JEUX['ohmatic']
    alt_re = re.compile(alt, re.I)
    idx = json.load(open(telecharger(J['index'], 'ohmatic/dataset.json'), encoding='utf-8'))['schematics']
    trouves = [r for r in idx if any(alt_re.search(c.get('value') or '') for c in (r.get('components') or []))]
    trouves.sort(key=lambda r: r.get('trust') != 'verified')
    avant, montres = set(VUS), Counter()
    for r in trouves:
        depot = depot_de(r.get('canonical_url'))
        if not place(depot, avant, montres):
            continue
        montres[depot] += 1
        confiance = ('vérifié (au moins deux familles de sources indépendantes)' if r.get('trust') == 'verified'
                     else "admis d'office (liste de départ d'Ohmatic)")
        prov = (r.get('provenance') or [{}])[0]
        entete = (f"== dépôt {depot} — {r.get('canonical_url')} ({prov.get('source_path', '')}, version "
                  f"{str(prov.get('revision', ''))[:7]})\n   source : Ohmatic — confiance : {confiance}")
        if r.get('format') == 'eagle_sch':
            sans_liaisons(entete, 'schéma Eagle : la chaîne ne sait pas encore en lire les liaisons.', depot)
            continue
        local = telecharger(J['fichiers'] + r['native_path'], 'ohmatic/' + r['native_path'])
        chemin = copie_schema(local, depot, os.path.splitext(local)[1], est_chemin=True)
        l = liaisons_kicad(chemin)
        if l is None:
            sans_liaisons(entete, "KiCad ne sait pas en sortir les liaisons (ancien format sans sa bibliothèque, ou schéma incomplet).", depot)
        elif not projet(depot, entete, l[0], broches_des_puces(*l), chemin):
            sans_liaisons(entete, "la puce n'est pas sur la feuille fournie (schéma en plusieurs feuilles).", depot)
    return f'{len(trouves)} schéma(s) trouvé(s), {len(montres)} dépôt(s) montré(s)'


def source_kicad9plus(alt):
    J = JEUX['kicad9plus']
    alt_re = re.compile(alt, re.I)
    trouves, avant, montres = 0, set(VUS), Counter()
    for url, nom in zip(J['index'], ('kicad9plus/permissive.jsonl', 'kicad9plus/copyleft.jsonl')):
        for ligne in open(telecharger(url, nom), encoding='utf-8'):
            d = json.loads(ligne)
            texte, meta = d['messages'][1]['content'], d.get('metadata') or {}
            if not any(alt_re.search(v) for v in re.findall(r'\((?:property "Value"|lib_id) "([^"]*)"', texte)):
                continue
            trouves += 1
            depot = depot_de('https://github.com/' + meta.get('repo', '?'))
            if not place(depot, avant, montres):
                continue
            entete = (f"== dépôt {depot} — {meta.get('source_url', '')}\n"
                      f"   source : kicad9plus — licence du projet : {meta.get('license_spdx', 'inconnue')}")
            chemin = copie_schema(texte, depot, '.kicad_sch')
            l = liaisons_kicad(chemin)
            if l is None:
                montres[depot] += 1
                sans_liaisons(entete, 'KiCad ne sait pas en sortir les liaisons (feuille seule, ou schéma incomplet).', depot)
            elif projet(depot, entete, l[0], broches_des_puces(*l), chemin):
                montres[depot] += 1
            # sinon, le motif n'était que dans le nom d'un symbole sans rapport : rien à montrer
    return f'{trouves} schéma(s) trouvé(s), {len(montres)} dépôt(s) montré(s)'


@functools.cache
def index_os():
    return pl.read_parquet(index_open_schematics()).with_columns(pl.col('name').str.to_lowercase().alias('depot'))


def source_open_schematics(alt):
    expr = f'(?i){alt}'
    idx = index_os()
    par_symbole = idx.filter(pl.col('components_used').list.eval(pl.element().str.contains(expr)).list.any())['depot']
    par_valeur, note = [], ''
    try:
        p = telecharger(JEUX['circuits']['index'], 'circuits/netlists.parquet')
        par_valeur = [depot_de(u) for u in pl.scan_parquet(p)
                      .filter(pl.col('source_url').str.contains('github.com') & pl.col('netlist_json').str.contains(expr))
                      .select('source_url').collect()['source_url']]
    except Exception as e:  # sans l'index des valeurs, on cherche encore par le nom du symbole
        note = f" (index des valeurs non lu : {type(e).__name__})"
    candidats = list(dict.fromkeys(list(par_symbole) + par_valeur))
    lignes = idx.filter(pl.col('depot').is_in(candidats))
    lisibles = set(lignes.filter(pl.col('extensions_used').list.contains('.kicad_sch'))['depot'])
    connus = set(lignes['depot'])
    anciens = [d for d in candidats if d in connus and d not in lisibles]
    hors_jeu = [d for d in candidats if d not in connus]
    file = [d for d in candidats if d in lisibles and d not in VUS]
    montres, essayes, absents = 0, 0, 0
    while file and montres < A.max and essayes < 4 * A.max:
        lot, file = file[:A.max - montres], file[A.max - montres:]
        essayes += len(lot)
        sous = lignes.filter(pl.col('depot').is_in(lot) & pl.col('extensions_used').list.contains('.kicad_sch'))
        textes = defaultdict(list)
        for f in sorted(set(sous['fichier'])):
            noms = sorted(set(sous.filter(pl.col('fichier') == f)['name']))
            d = (pl.scan_parquet(fichier_open_schematics(f)).select(['name', 'description', 'schematic'])
                 .filter(pl.col('name').is_in(noms) & pl.col('schematic').str.contains(expr)).collect())
            for nom, desc, sch in d.iter_rows():
                textes[depot_de(nom)].append((nom, desc, sch))
        for depot in lot:
            feuilles, vu = textes.get(depot, [])[:4], False   # au plus 4 schémas (versions, cartes) par dépôt
            for k, (nom, desc, sch) in enumerate(feuilles, 1):
                desc = ' '.join((desc or '').split())
                entete = (f"== dépôt {nom}" + (f", schéma {k} sur {len(feuilles)}" if len(feuilles) > 1 else '')
                          + f" — https://github.com/{nom}\n   source : Open Schematics — "
                          + (f"le dépôt se décrit ainsi : « {desc[:160]}{'…' if len(desc) > 160 else ''} »" if desc
                             else "le dépôt n'a pas de description"))
                chemin = copie_schema(sch, depot, '.kicad_sch')
                l = liaisons_kicad(chemin)
                if l is None:
                    sans_liaisons(entete, "KiCad ne sait pas en sortir les liaisons (schéma incomplet ou d'une autre version).", depot)
                    vu = True
                elif projet(depot, entete, l[0], broches_des_puces(*l), chemin):
                    vu = True
            montres += vu
            absents += not vu   # la valeur était sur une autre feuille du dépôt, que le jeu n'a pas gardée
        info(f'  open-schematics, « {alt} » : {montres} montré(s) sur {essayes} essayé(s)')
    n_sym = len(set(par_symbole))
    return (f'{len(candidats)} dépôt(s) trouvé(s) ({n_sym} par le nom du symbole, {len(candidats) - n_sym} de plus par '
            f'la valeur{note})' + (f', dont {len(anciens)} en ancien format KiCad (.sch, pas lu)' if anciens else '')
            + (f', {len(hors_jeu)} absent(s) d\'Open Schematics' if hors_jeu else '') + f' ; {montres} montré(s)'
            + (f', {absents} sans la puce sur la feuille gardée par le jeu' if absents else ''))


SOURCES = {'ohmatic': source_ohmatic, 'kicad9plus': source_kicad9plus, 'open-schematics': source_open_schematics}

t0 = time.time()
for s in A.sources.split(','):
    t, parts = time.time(), []
    for alt in alternatives(MOTIF):
        try:
            parts.append((f'« {alt} » : ' if len(alternatives(MOTIF)) > 1 else '') + SOURCES[s](alt))
        except Exception as e:  # une source injoignable ne doit pas empêcher les autres
            parts.append(f'source non lue ({type(e).__name__} : {str(e)[:120]})')
    BILAN.append(f'  - {JEUX[s]["nom"]}, {JEUX[s]["page"]} :' + ''.join(f'\n      {x}' for x in parts))
    info(BILAN[-1], f'({time.time() - t:.0f} s)')

synthese, broches_vues = [], 0
for fam in sorted(COMPTES, key=lambda f: -len(COMPTES[f])):
    synthese.append(f'  {fam} : {len(COMPTES[fam])} projet(s) compté(s), de {len({auteur(d) for d in COMPTES[fam]})} auteur(s)')
    synthese += brochage_different(fam)
    non_reliees = []
    for cle in sorted((c for c in SYNTH if c[0] == fam), key=lambda c: (ordre(c[1]), c[2])):
        vals = sorted(((v, len(d)) for v, d in SYNTH[cle].items() if len(d) >= 2), key=lambda x: -x[1])
        nom_broche = (cle[1] or 'sans numéro') + (f' ({cle[2]})' if cle[2] else '')
        if [v for v, _ in vals] == ['non reliée']:
            non_reliees.append(nom_broche)
        elif vals:
            synthese.append(f'    broche {nom_broche} : ' + ', '.join(f'{v} ({n} auteurs)' for v, n in vals[:4]))
            broches_vues += 1
    if non_reliees:
        synthese.append('    laissées non reliées par au moins deux auteurs : ' + ', '.join(non_reliees))
        broches_vues += 1

tete = [f'Montages réels de « {MOTIF} » — {time.strftime("%d/%m/%Y")}',
        'Projets publiés : à comparer, pas à recopier les yeux fermés. Chaque projet garde sa licence : on lit et on cite.',
        "Toutes les liaisons ci-dessous sortent de KiCad, lisant le schéma d'origine. Une feuille par schéma : ce qui passe",
        "par une autre feuille apparaît comme « réseau X, rien d'autre sur cette feuille ».",
        '', "Sources, de la plus sûre à la moins sûre (un dépôt n'est pris que dans une source) :", *BILAN, '',
        'Ce qui revient chez au moins deux auteurs différents (composants branchés sur chaque broche ; deux dépôts',
        "d'un même compte GitHub comptent pour un ; les réseaux d'alimentation partagés par plus de 12 composants",
        'ne sont pas comptés) :',
        *(synthese if broches_vues else synthese + ['  rien : pas assez de projets, ou trop différents.']),
        '', 'Le détail, projet par projet :', '']
open(os.path.join(SORTIE, 'montages.txt'), 'w', encoding='utf-8').write('\n'.join(tete + RAPPORT) + '\n')
print('\n'.join(tete + RAPPORT))
info(f'({time.time() - t0:.0f} s en tout)')
