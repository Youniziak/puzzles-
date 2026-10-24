"""Chaîne puzzle, étape 6 — « banc de test à pointes » : mesurer toutes les sorties de la carte sans viser une
pastille de 1,5 mm avec la pointe du multimètre.
La carte se pose dans un socle imprimé, sur des tétons qui entrent dans ses trous de fixation. Au-dessus, une petite
« carte du banc » porte une pointe à ressort (type P75) sur chaque sortie, et une sur la couronne d'un trou de fixation
relié à la masse ; ses pistes mènent chaque pointe à une borne, une pastille ronde. Un porte-pointes imprimé guide les
pointes ; un capot imprimé couvre la carte du banc : au-dessus de chaque borne, un entonnoir guide la pointe du
multimètre, avec le numéro de la sortie en braille et en chiffres en relief. Quatre vis et quatre écrous papillon
serrent le tout à la main ; des colonnes fixent la hauteur, donc l'enfoncement des pointes.
Principe repris de bancs publiés (gCore et wESP32 sur hackaday.io, OpenFixture, pogojig) ; les entonnoirs, le braille
et le serrage à la main sont propres à la chaîne puzzle.
Le script :
  1. lit la carte : sorties, trous de fixation, modèles 3D des composants (hauteurs) ;
  2. dessine la carte du banc dans KiCad (pointes, bornes, trous des vis), la fait router par Freerouting, contrôler
     par KiCad, et préparer pour l'usine par KiKit ;
  3. fait les trois pièces à imprimer avec CadQuery : socle, porte-pointes, capot ;
  4. contrôle le tout et écrit la notice (banc-test.txt).
Réglages : bibliotheque/regles/banc_test.json ; dimensions du braille : maquette.json. Sorties : dossier_projet/banc-test/.
Usage : python3 banc_test.py cartes/ma-carte.json dossier_projet/carte.kicad_pcb chemin/freerouting.jar chemin/kikit"""
import json, math, os, re, subprocess, sys, time
import cadquery as cq
import numpy as np
import pcbnew
import trimesh
from scipy import ndimage
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union
from description import Carte
from modeles3d import Carte3D

CARTE = Carte(sys.argv[1])
PCB, JAR, KIKIT = os.path.abspath(sys.argv[2]), os.path.abspath(sys.argv[3]), sys.argv[4]
DOSSIER_REGLES = os.path.join(CARTE.bibliotheque, 'regles')
B = json.load(open(os.path.join(DOSSIER_REGLES, 'banc_test.json'), encoding='utf-8'))
MQ = json.load(open(os.path.join(DOSSIER_REGLES, 'maquette.json'), encoding='utf-8'))
BR, POLICE = MQ['braille'], MQ['texte']['police']
P, CB, VS, SO, PP, CA = B['pointe'], B['carte_banc'], B['vis'], B['socle'], B['porte_pointes'], B['capot']
SORTIE = os.path.join(os.path.dirname(PCB), 'banc-test')
os.makedirs(SORTIE, exist_ok=True)
avert, controles = [], []
nb_ko = 0
def mm(v):
    return str(round(v, 1)).replace('.', ',')
def ctrl(ok, texte):
    global nb_ko
    nb_ko += not ok
    controles.append(('✓ ' if ok else '✗ ') + texte)

K = Carte3D(CARTE, PCB)
W, H, EP = K.W, K.H, K.EP

# ---------- 1. points de mesure : chaque sortie, et la masse sur la couronne d'un trou de fixation
ordre = lambda r: [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', r)]
refs = sorted({CARTE.repere(b, r) for b in CARTE.blocs for r in b.bloc.get('non_poses', [])}, key=ordre)
points = []
for ref in refs:
    fp = K.board.FindFootprintByReference(ref)
    pad = next(iter(fp.Pads()))
    x, y = K.xy(pad.GetPosition())
    n = re.search(r'(\d+)$', ref)
    points.append(dict(nom=n.group(1) if n else ref, x=x, y=y, signal=pad.GetNetname(), ref=ref, masse=False))
trous_masse = [t for t in K.trous if t[3]]
if trous_masse:
    cx, cy = np.mean([p['x'] for p in points]), np.mean([p['y'] for p in points])
    ref_t, (hx, hy), d_trou, _ = min(trous_masse, key=lambda t: math.hypot(t[1][0] - cx, t[1][1] - cy))
    d_cuivre = (CARTE.trou or {}).get('diametre_cuivre_mm', d_trou + 2.8)
    r_c = (d_trou / 2 + d_cuivre / 2) / 2                       # milieu de la couronne de cuivre
    a = math.atan2(cy - hy, cx - hx)
    points.insert(0, dict(nom='masse', x=hx + r_c * math.cos(a), y=hy + r_c * math.sin(a), signal=CARTE.masse, ref=ref_t, masse=True))
else:
    avert.append("aucun trou de fixation relié à la masse : pas de borne « masse » ; prendre la masse sur le corps de la prise USB")
if not K.trous:
    avert.append("la carte n'a pas de trou de fixation : rien pour la tenir en place dans le socle (ajouter « trous_fixation »)")

print('… étape 2 : hauteurs', time.strftime('%H:%M:%S'), flush=True)
# ---------- 2. hauteurs
L, C, EPJ = P['longueur_mm'], P['course_travail_mm'], CB['epaisseur_mm']
ref_haut, z_haut = K.plus_haut
ZJ = L - C - EPJ                      # dessous de la carte du banc : la pointe, enfoncée de C, touche la sortie (z = 0)
ZH0 = z_haut + PP['au_dessus_du_plus_haut_mm']
if ZJ - ZH0 < PP['epaisseur_min_mm']:
    sys.exit(f"Pointes trop courtes pour cette carte : le plus haut composant ({ref_haut}, {mm(z_haut)} mm) laisse "
             f"{mm(ZJ - ZH0)} mm pour le porte-pointes (il en faut {PP['epaisseur_min_mm']}). Prendre des pointes plus longues "
             "et changer « pointe » dans banc_test.json.")
ZC0, ZC1 = ZJ + EPJ, ZJ + EPJ + CA['epaisseur_mm']
SOUS = max(SO['sous_la_carte_min_mm'], K.pattes + SO['jeu_sous_les_pattes_mm'])
ZS1 = -(EP + SOUS)
ZS0 = ZS1 - SO['fond_mm']

# ---------- couloirs : devant chaque prise et passage de fils déclarés (« boitier » dans bloc.json), rien ne doit gêner
couloirs = []
for b in CARTE.blocs:
    for genre in ('ouvertures', 'fils'):
        for e in b.bloc.get('boitier', {}).get(genre, []):
            ref = CARTE.repere(b, e['ref'])
            q = K.boites.get(ref)
            if q is None:
                continue
            d = {'gauche': q.xmin, 'droite': W - q.xmax, 'bas': q.ymin, 'haut': H - q.ymax}
            face = min(d, key=d.get)
            a0, a1 = (q.ymin, q.ymax) if face in ('gauche', 'droite') else (q.xmin, q.xmax)
            larg = max(a1 - a0, e.get('fiche_mm', [0, 0])[0]) + 6
            couloirs.append((face, (a0 + a1) / 2 - larg / 2, (a0 + a1) / 2 + larg / 2, e['texte']))
def rect_couloir(face, a0, a1, m):
    return {'gauche': box(-m - 1, a0, 0, a1), 'droite': box(W, a0, W + m + 1, a1),
            'bas': box(a0, -m - 1, a1, 0), 'haut': box(a0, H, a1, H + m + 1)}[face]

# ---------- 3. étiquettes : numéro et nom du signal en lettres en relief ; braille (liblouis) en plus, si on le veut
import braille as BRL
TABLE_BR = CA.get('table_braille', BRL.TABLE)
AVEC_BRAILLE = CA.get('braille', True)
NOMS_COURTS = CARTE.donnees.get('noms_courts', {})
def nom_court(signal):
    """Nom court d'une liaison pour l'écrire sur le capot : celui de la carte (« noms_courts »), sinon la fin du nom."""
    return NOMS_COURTS.get(signal, signal.split('_')[-1][:6])
_textes, _taille_police = {}, {}
def texte_relief(txt, hauteur):
    """Lettres ou chiffres en relief (CadQuery), centrés sur l'origine ; « hauteur » = hauteur des capitales et des chiffres."""
    if (txt, hauteur) not in _textes:
        if hauteur not in _taille_police:
            essai = cq.Workplane('XY').text('HM0123456789', 10, 1, fontPath=POLICE).val().BoundingBox()
            _taille_police[hauteur] = 10 * hauteur / (essai.ymax - essai.ymin)
        s = cq.Workplane('XY').text(txt, _taille_police[hauteur], CA['chiffres_relief_mm'] + 0.01, fontPath=POLICE,
                                    halign='center', valign='center').val()
        bb = s.BoundingBox()
        _textes[(txt, hauteur)] = s.translate(cq.Vector(-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))
    return _textes[(txt, hauteur)]

RT = CA['entonnoir_haut_mm'] / 2
G = CA['ecart_mm']
def gabarit(p):
    """Une borne, de haut en bas : l'entonnoir, le braille (si on le veut), le numéro, puis le nom du signal en lettres."""
    if p['masse']:
        tb, lignes = CA['masse']['braille'], [(CA['masse']['relief'], CA['chiffres_hauteur_mm'])]
    else:
        tb, lignes = p['nom'], [(p['nom'], CA['chiffres_hauteur_mm']), (nom_court(p['signal']), CA['noms_hauteur_mm'])]
    bw, bh = BRL.taille(tb, BR, TABLE_BR) if AVEC_BRAILLE else (0, 0)
    mesures = []
    for txt, h in lignes:
        bb = texte_relief(txt, h).BoundingBox()
        mesures.append((txt, h, bb.xmax - bb.xmin, bb.ymax - bb.ymin))
    largeur = max([2 * RT, bw] + [m[2] for m in mesures])
    hauteur = 2 * RT + (G + bh if AVEC_BRAILLE else 0) + sum(G + m[3] for m in mesures)
    return dict(tb=tb, bw=bw, bh=bh, lignes=mesures, w=largeur, h=hauteur)
for p in points:
    p.update(gabarit=gabarit(p))

# ---------- 4. disposition du banc : vis aux coins, bornes en ordre de lecture ; on agrandit si ça ne tient pas
def disposer(m):
    zone = box(-m + 2, -m + 2, W + m - 2, H + m - 2)
    coin = Polygon([(-m, H + m - CA['coin_repere_mm']), (-m, H + m), (-m + CA['coin_repere_mm'], H + m)]).buffer(2)
    r_col = VS['colonne_diametre_mm'] / 2
    vis = []
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        x = -m + VS['retrait_du_bord_mm'] if sx < 0 else W + m - VS['retrait_du_bord_mm']
        y = -m + VS['retrait_du_bord_mm'] if sy < 0 else H + m - VS['retrait_du_bord_mm']
        place = None
        for d in np.arange(0, 20.01, 0.5):                     # glisser le long du bord si un couloir la gêne
            for dx, dy in ((0, 0), (-sx * d, 0), (0, -sy * d)):
                c = Point(x + dx, y + dy).buffer(r_col + 1)
                if (not c.intersects(K.contour) and not any(c.intersects(rect_couloir(f, a0, a1, m)) for f, a0, a1, _ in couloirs)
                        and not c.intersects(coin)):
                    place = (float(x + dx), float(y + dy))
                    break
            if place:
                break
        if place is None:
            return None
        vis.append(place)
    gardes = [Point(v).buffer(VS['garde_autour_mm']) for v in vis] + [coin]
    utilisable = zone.difference(unary_union(gardes))
    # bornes en rangées alignées, dans l'ordre de lecture (gauche → droite, haut → bas) : la masse d'abord, puis 1, 2, 3…
    # si une place est prise (pointe dessous, vis), la borne glisse plus loin dans la même rangée, sans changer l'ordre
    poses, places = [], []
    def libre(fx, fy, g):
        r = box(fx - g['w'] / 2, fy + RT - g['h'], fx + g['w'] / 2, fy + RT)
        if not utilisable.contains(r) or any(r.buffer(G).intersects(o) for o in places):
            return None
        if any(math.hypot(fx - q['x'], fy - q['y']) < CB['ecart_borne_pointe_mm'] for q in points):
            return None
        return r
    h_rangee = max(p['gabarit']['h'] for p in points)
    y, i = H + m - 2, 0
    while i < len(points) and y - h_rangee >= -m + 2:
        x = -m + 2
        while i < len(points) and x + points[i]['gabarit']['w'] <= W + m - 2:
            g = points[i]['gabarit']
            r = libre(x + g['w'] / 2, y - RT, g)
            if r is None:
                x += 0.5
                continue
            places.append(r)
            poses.append((x + g['w'] / 2, y - RT))
            x += g['w'] + 3
            i += 1
        y -= h_rangee + 2
    if i < len(points):
        return None
    return vis, poses

m = CB['marge_autour_mm']
res = None
while m <= CB['marge_max_mm'] and res is None:
    res = disposer(m)
    if res is None:
        m += 5
if res is None:
    sys.exit(f"Les {len(points)} bornes ne tiennent pas sur une carte du banc de moins de {mm(W + 2 * CB['marge_max_mm'])} mm de large.")
VIS, BORNES = res
for p, (fx, fy) in zip(points, BORNES):
    p['fx'], p['fy'] = fx, fy
MARGE = m
JX0, JY0, JX1, JY1 = -MARGE, -MARGE, W + MARGE, H + MARGE
if MARGE > CB['marge_autour_mm']:
    avert.append(f"carte du banc agrandie : {mm(MARGE)} mm autour de la carte, pour que toutes les bornes tiennent")

print('… étape 5 : carte du banc', time.strftime('%H:%M:%S'), flush=True)
# ---------- 5. la carte du banc dans KiCad
JIG = os.path.join(SORTIE, 'carte-banc.kicad_pcb')
mmk = pcbnew.FromMM
def V(x, y):
    return pcbnew.VECTOR2I(mmk(float(x)), mmk(-float(y)))
jb = pcbnew.BOARD()
jb.SetCopperLayerCount(2)
k = CARTE.regles['kicad']
ds = jb.GetDesignSettings()
ds.m_MinClearance = mmk(k['min_clearance']); ds.m_TrackMinWidth = mmk(k['min_track_width'])
ds.m_MinThroughDrill = mmk(k['min_through_hole_diameter']); ds.m_CopperEdgeClearance = mmk(k['min_copper_edge_clearance'])
ds.m_HoleClearance = mmk(k['min_hole_clearance']); ds.m_ViasMinSize = mmk(k['min_via_diameter'])
cd = CARTE.regles['classe_par_defaut']
nc = ds.m_NetSettings.GetDefaultNetclass()
nc.SetClearance(mmk(max(cd['clearance'], 0.2))); nc.SetTrackWidth(mmk(CB['piste_mm']))
nc.SetViaDiameter(mmk(cd['via_diameter'])); nc.SetViaDrill(mmk(cd['via_drill']))
RJ = CB['rayon_coins_mm']
def trait(a, b_):
    s = pcbnew.PCB_SHAPE(jb); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetStart(V(*a)); s.SetEnd(V(*b_)); s.SetWidth(mmk(0.05)); jb.Add(s)
def arc(c, debut, fin):
    s = pcbnew.PCB_SHAPE(jb); s.SetShape(pcbnew.SHAPE_T_ARC); s.SetLayer(pcbnew.Edge_Cuts)
    mil = (c[0] + (debut[0] + fin[0] - 2 * c[0]) / math.sqrt(2), c[1] + (debut[1] + fin[1] - 2 * c[1]) / math.sqrt(2))
    s.SetArcGeometry(V(*debut), V(*mil), V(*fin)); s.SetWidth(mmk(0.05)); jb.Add(s)
trait((JX0 + RJ, JY0), (JX1 - RJ, JY0)); trait((JX1, JY0 + RJ), (JX1, JY1 - RJ))
trait((JX1 - RJ, JY1), (JX0 + RJ, JY1)); trait((JX0, JY1 - RJ), (JX0, JY0 + RJ))
arc((JX1 - RJ, JY0 + RJ), (JX1 - RJ, JY0), (JX1, JY0 + RJ)); arc((JX1 - RJ, JY1 - RJ), (JX1, JY1 - RJ), (JX1 - RJ, JY1))
arc((JX0 + RJ, JY1 - RJ), (JX0 + RJ, JY1), (JX0, JY1 - RJ)); arc((JX0 + RJ, JY0 + RJ), (JX0, JY0 + RJ), (JX0 + RJ, JY0))

def empreinte(ref, valeur, nom_lib, x, y):
    fp = pcbnew.FOOTPRINT(jb)
    fp.SetFPID(pcbnew.LIB_ID('banc', nom_lib)); fp.SetReference(ref); fp.SetValue(valeur)
    fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    return fp
def pastille(fp, diam, trou=None, net=None, npth=False):
    pad = pcbnew.PAD(fp); pad.SetNumber('' if npth else '1')
    pad.SetShape(pcbnew.F_Cu, pcbnew.PAD_SHAPE_CIRCLE)
    if trou:
        pad.SetDrillShape(pcbnew.PAD_DRILL_SHAPE_CIRCLE); pad.SetDrillSize(pcbnew.VECTOR2I(mmk(trou), mmk(trou)))
        if npth:
            pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH); pad.SetLayerSet(pad.UnplatedHoleMask())
        else:
            pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH); pad.SetLayerSet(pad.PTHMask())
    else:
        pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.F_Mask); pad.SetLayerSet(ls)
    pad.SetSize(pcbnew.F_Cu, pcbnew.VECTOR2I(mmk(diam), mmk(diam)))
    fp.Add(pad)
    return pad
nets = {}
a_relier = []
for i, p in enumerate(points, 1):
    nom_net = 'MASSE' if p['masse'] else p['ref']
    n = pcbnew.NETINFO_ITEM(jb, nom_net); jb.Add(n); nets[nom_net] = n
    fp = empreinte(f'P{i}', P['modele'].split()[0], 'Pointe_P75', p['x'], p['y'])
    pa = pastille(fp, P['pastille_carte_mm'], P['trou_carte_mm'])
    fp.SetPosition(V(p['x'], p['y'])); jb.Add(fp); pa.SetNet(n)
    fb = empreinte(f'B{i}', f"borne {p['nom']}", 'Borne_ronde', p['fx'], p['fy'])
    pb = pastille(fb, CB['borne_diametre_mm'])
    fb.SetPosition(V(p['fx'], p['fy'])); jb.Add(fb); pb.SetNet(n)
    a_relier.append(nom_net)
for i, (vx, vy) in enumerate(VIS, 1):
    fv = empreinte(f'V{i}', 'trou de vis M3', 'Trou_vis', vx, vy)
    pastille(fv, VS['trou_mm'], VS['trou_mm'], npth=True)
    fv.SetAttributes(pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    fv.SetPosition(V(vx, vy)); jb.Add(fv)
tx = pcbnew.PCB_TEXT(jb)
tx.SetText(f"Banc de test — {CARTE.nom}"); tx.SetLayer(pcbnew.F_SilkS); tx.SetPosition(V((JX0 + JX1) / 2, JY0 + 3))
tx.SetTextSize(pcbnew.VECTOR2I(mmk(1.5), mmk(1.5))); jb.Add(tx)
pcbnew.SaveBoard(JIG, jb)
projet = {'board': {'design_settings': {'rules': k}},
          'net_settings': {'classes': [{'name': 'Default', 'clearance': max(cd['clearance'], 0.2), 'track_width': CB['piste_mm'],
                                        'via_diameter': cd['via_diameter'], 'via_drill': cd['via_drill']}], 'netclass_patterns': []}}
json.dump(projet, open(JIG[:-len('.kicad_pcb')] + '.kicad_pro', 'w'), indent=2)

def drc():
    rap = os.path.join(SORTIE, 'carte-banc-controle.json')
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-error', '--output', rap, JIG], capture_output=True, check=True)
    return json.load(open(rap))
for passage in (1, 2, 3):
    if not drc()['unconnected_items']:
        break
    jb = pcbnew.LoadBoard(JIG)
    dsn, ses = JIG[:-len('.kicad_pcb')] + '.dsn', JIG[:-len('.kicad_pcb')] + '.ses'
    assert pcbnew.ExportSpecctraDSN(jb, dsn), "export DSN impossible"
    with open(os.path.join(SORTIE, f'carte-banc-freerouting-{passage}.log'), 'w') as log:
        subprocess.run(['java', '-jar', JAR, '--gui.enabled=false', '--usage_and_diagnostic_data.disable_analytics=true',
                        '--api_server.enabled=false', '--router.optimizer.enabled=false', '-mp', '30', '-de', dsn, '-do', ses],
                       stdout=log, stderr=subprocess.STDOUT, timeout=1200, check=True)
    assert pcbnew.ImportSpecctraSES(jb, ses), "KiCad n'a pas pu relire le résultat de Freerouting"
    pcbnew.SaveBoard(JIG, jb)
d = drc()
ctrl(not d['violations'] and not d['unconnected_items'],
     f"carte du banc : KiCad ne trouve {'aucune erreur' if not d['violations'] else str(len(d['violations'])) + ' erreur(s)'}, "
     f"{len(d['unconnected_items'])} liaison(s) manquante(s) ; {len(points)} pointes reliées chacune à sa borne")
jb = pcbnew.LoadBoard(JIG)
bonnes = 0
for i, p in enumerate(points, 1):
    np_ = next(iter(jb.FindFootprintByReference(f'P{i}').Pads())).GetNetname()
    nb_ = next(iter(jb.FindFootprintByReference(f'B{i}').Pads())).GetNetname()
    bonnes += np_ == nb_ == ('MASSE' if p['masse'] else p['ref'])
ctrl(bonnes == len(points), f"chaque borne porte la même liaison que sa pointe ({bonnes} sur {len(points)})")
FAB = os.path.join(SORTIE, 'fabrication-carte-banc')
rk = subprocess.run([KIKIT, 'fab', 'jlcpcb', '--no-drc', JIG, FAB], capture_output=True, text=True)
fichiers_fab = sorted(os.listdir(FAB)) if rk.returncode == 0 and os.path.isdir(FAB) else []
ctrl(bool(fichiers_fab), 'fichiers pour l\'usine de la carte du banc (KiKit) : ' + (', '.join(fichiers_fab) if fichiers_fab else
     'échec — ' + ((rk.stdout + rk.stderr).strip().splitlines() or ['?'])[-1]))

print('… étape 6 : pièces', time.strftime('%H:%M:%S'), flush=True)
# ---------- 6. pièces imprimées (CadQuery)
def dalle(z0, z1):
    return (cq.Workplane('XY').workplane(offset=z0).center((JX0 + JX1) / 2, (JY0 + JY1) / 2)
            .rect(JX1 - JX0, JY1 - JY0).extrude(z1 - z0).edges('|Z').fillet(RJ).val())
def cylindre(x, y, r, z0, z1):
    return cq.Solid.makeCylinder(r, z1 - z0, cq.Vector(x, y, z0))
def couloirs_solides(z0, z1):
    return [cq.Solid.makeBox(c.bounds[2] - c.bounds[0], c.bounds[3] - c.bounds[1], z1 - z0, cq.Vector(c.bounds[0], c.bounds[1], z0))
            for c in (rect_couloir(f, a0, a1, MARGE) for f, a0, a1, _ in couloirs)]

# appuis sous la carte : près de chaque pointe, là où le dessous est libre (pas de patte)
RA = SO['plot_appui_diametre_mm'] / 2
gene_dessous = unary_union([g.buffer(0.5 + RA) for g in K.emprise_dessous] + [Point(t[1]).buffer(4 + RA) for t in K.trous])
libre_dessous = K.contour.buffer(-(1 + RA)).difference(gene_dessous)
appuis = []
grille = [(float(x), float(y)) for x in np.arange(0, W, 0.5) for y in np.arange(0, H, 0.5)]
for p in points:
    if p['masse']:
        continue
    pres = sorted((math.hypot(x - p['x'], y - p['y']), (x, y)) for x, y in grille if abs(x - p['x']) <= SO['plot_appui_recherche_mm'] and abs(y - p['y']) <= SO['plot_appui_recherche_mm'])
    pt = next((q for dq, q in pres if dq <= SO['plot_appui_recherche_mm'] and libre_dessous.contains(Point(q))), None)
    if pt and all(math.hypot(pt[0] - a[0], pt[1] - a[1]) >= 6 for a in appuis):
        appuis.append(pt)

print('… étape 6b : socle', time.strftime('%H:%M:%S'), flush=True)
r_vis = VS['trou_mm'] / 2
socle = dalle(ZS0, ZS1)
for vx, vy in VIS:
    socle = socle.fuse(cylindre(vx, vy, VS['colonne_diametre_mm'] / 2, ZS1 - 0.01, ZH0))
for ref_t, (hx, hy), d_t, _ in K.trous:
    socle = socle.fuse(cylindre(hx, hy, SO['plot_trou_diametre_mm'] / 2, ZS1 - 0.01, -EP))
    socle = socle.fuse(cylindre(hx, hy, (d_t - SO['teton_jeu_mm']) / 2, -EP - 0.01, SO['teton_depasse_mm']))
for ax, ay in appuis:
    socle = socle.fuse(cylindre(ax, ay, RA, ZS1 - 0.01, -EP))
hexa = lambda x, y, z0, h: (cq.Workplane('XY').workplane(offset=z0).center(x, y)
                            .polygon(6, (VS['tete_sur_plats_mm'] + 0.4) / math.cos(math.pi / 6)).extrude(h).val())
for vx, vy in VIS:
    socle = socle.cut(cylindre(vx, vy, r_vis, ZS0 - 1, ZH0 + 1)).cut(hexa(vx, vy, ZS0 - 0.01, VS['tete_hauteur_mm'] + 0.3))
for c in couloirs_solides(ZS0 - 1, ZH0 + 1):
    socle = socle.cut(c)

porte = dalle(ZH0, ZJ)
for p in points:
    porte = porte.cut(cylindre(p['x'], p['y'], (P['diametre_corps_mm'] + P['jeu_guide_mm']) / 2, ZH0 - 1, ZJ + 1))
for vx, vy in VIS:
    porte = porte.cut(cylindre(vx, vy, r_vis, ZH0 - 1, ZJ + 1))
for c in couloirs_solides(ZH0 - 1, ZJ + 1):
    porte = porte.cut(c)
for ref, q in K.boites.items():                       # au cas où : rien ne doit entrer dans le porte-pointes
    if q.zmax > ZH0 - 0.2:
        porte = porte.cut(cq.Solid.makeBox(q.xlen + 1, q.ylen + 1, q.zmax - ZH0 + 0.7, cq.Vector(q.xmin - 0.5, q.ymin - 0.5, ZH0 - 0.1)))

print('… étape 6c : capot', time.strftime('%H:%M:%S'), flush=True)
capot = dalle(ZC0, ZC1)
cr = CA['coin_repere_mm']
coupe_coin = (cq.Workplane('XY').workplane(offset=ZC0 - 1).polyline([(JX0 - 1, JY1 - cr), (JX0 - 1, JY1 + 1), (JX0 + cr, JY1 + 1)])
              .close().extrude(ZC1 - ZC0 + 2).val())
capot = capot.cut(coupe_coin)
for vx, vy in VIS:
    capot = capot.cut(cylindre(vx, vy, r_vis, ZC0 - 1, ZC1 + 1))
for p in points:
    capot = capot.cut(cylindre(p['x'], p['y'], CA['logement_pointe_mm'] / 2, ZC0 - 0.01, ZC0 + CA['logement_profondeur_mm']))
    hz = ZC1 - ZC0 + 0.2
    rb = CA['entonnoir_bas_mm'] / 2
    if p['masse']:                                     # entonnoir carré pour la masse : on le reconnaît au toucher
        ent = (cq.Workplane('XY').workplane(offset=ZC0 - 0.1).center(p['fx'], p['fy']).rect(2 * rb, 2 * rb)
               .workplane(offset=hz).rect(2 * RT, 2 * RT).loft().val())
    else:
        ent = cq.Solid.makeCone(rb, RT, hz, cq.Vector(p['fx'], p['fy'], ZC0 - 0.1))
    capot = capot.cut(ent)
# point braille : petit cylindre aux bords bien arrondis (une demi-sphère a un pôle que le maillage STL ferme mal)
_rb = BR['point_diametre_mm'] / 2
point_braille = (cq.Workplane('XY').circle(_rb).extrude(_rb + 0.01).faces('>Z').edges().fillet(_rb * 0.75).val())
nb_points_braille = {}
ajouts = []
for p in points:
    g = p['gabarit']
    y = p['fy'] - RT                                                   # sous l'entonnoir
    if AVEC_BRAILLE:
        yb = y - G - BR['point_diametre_mm'] / 2                        # rangée des points 1 et 4
        pts = BRL.points(g['tb'], p['fx'] - g['bw'] / 2 + BR['point_diametre_mm'] / 2, yb, BR, TABLE_BR)
        nb_points_braille[p['nom']] = (len(pts), box(p['fx'] - g['bw'] / 2, y - G - g['bh'], p['fx'] + g['bw'] / 2, y - G))
        for x, yy in pts:
            ajouts.append(point_braille.translate(cq.Vector(x, yy, ZC1 - 0.01)))
        y -= G + g['bh']
    p['cadres_relief'] = []
    for txt, h, tw, th in g['lignes']:
        yt = y - G - th / 2
        ajouts.append(texte_relief(txt, h).translate(cq.Vector(p['fx'], yt, ZC1 - 0.01)))
        p['cadres_relief'].append(box(p['fx'] - tw / 2, yt - th / 2, p['fx'] + tw / 2, yt + th / 2))
        y -= G + th
print('… étape 6d : fusion braille', time.strftime('%H:%M:%S'), flush=True)
capot = capot.fuse(*ajouts).clean()

print('… étape 6e : export', time.strftime('%H:%M:%S'), flush=True)
pieces = {'banc-socle.stl': socle, 'banc-porte-pointes.stl': porte, 'banc-capot.stl': capot}
maillages = {}
for nom, s in pieces.items():
    chemin = os.path.join(SORTIE, nom)
    cq.exporters.export(cq.Workplane('XY').add(s), chemin, tolerance=0.05, angularTolerance=0.2)
    maillages[nom] = trimesh.load(chemin)
ctrl(all(mg.is_watertight for mg in maillages.values()), 'pièces imprimées fermées (prêtes à imprimer) : '
     + ', '.join(f"{n[5:-4]} {'oui' if mg.is_watertight else 'NON'}" for n, mg in maillages.items()))

print('… étape 7 : contrôles', time.strftime('%H:%M:%S'), flush=True)
# ---------- 7. contrôles
ctrl(C <= P['course_totale_mm'] - 0.5, f"enfoncement des pointes : {mm(C)} mm sur {mm(P['course_totale_mm'])} possibles")
genants = []
for p in points:
    for ref, q in K.boites.items():
        if ref in refs or q.zmax <= 0.05:
            continue
        r = P['diametre_corps_mm'] / 2 + 0.2
        if q.xmin - r < p['x'] < q.xmax + r and q.ymin - r < p['y'] < q.ymax + r and q.zmax > 0.05:
            genants.append(f"{p['nom']} ↔ {ref}")
ctrl(not genants, 'chaque pointe descend jusqu\'à sa sortie sans frôler un composant' if not genants else
     'pointe(s) qui frôlent un composant (boîtes 3D, à regarder) : ' + ', '.join(genants))
mini = min(math.hypot(p['fx'] - q['x'], p['fy'] - q['y']) for p in points for q in points)
ctrl(mini >= CB['ecart_borne_pointe_mm'] - 0.01, f"entonnoirs loin des pointes : {mm(mini)} mm au plus près")
ctrl(CA['entonnoir_bas_mm'] < CB['borne_diametre_mm'] - 0.2,
     f"le bas de chaque entonnoir (⌀ {mm(CA['entonnoir_bas_mm'])} mm) tombe sur sa borne (⌀ {mm(CB['borne_diametre_mm'])} mm)")
gene_c = [f for f, a0, a1, _ in couloirs for v in VIS if Point(v).buffer(VS['colonne_diametre_mm'] / 2).intersects(rect_couloir(f, a0, a1, MARGE))]
ctrl(not gene_c, f"colonnes hors du passage des prises et des fils ({len(couloirs)} passage(s) laissés libres)")
# carte radio posée : sur ses appuis, sans toucher le socle ailleurs, et les tétons dans les trous
so = maillages['banc-socle.stl']
gx, gy = np.meshgrid(np.arange(0.5, W, 1.5), np.arange(0.5, H, 1.5))
dans = np.array([(x, y, -EP / 2) for x, y in zip(gx.ravel(), gy.ravel())
                 if K.contour.buffer(-0.3).contains(Point(x, y)) and all(math.hypot(x - t[1][0], y - t[1][1]) > t[2] / 2 + 0.1 for t in K.trous)])
ctrl(not so.contains(dans).any(), 'la carte se pose dans le socle sans rien toucher d\'autre que ses appuis et les tétons')
pr = maillages['banc-porte-pointes.stl']
pts_c = []
for ref, q in K.boites.items():
    xs, ys, zs = np.arange(q.xmin + 0.3, q.xmax - 0.29, 1.0), np.arange(q.ymin + 0.3, q.ymax - 0.29, 1.0), np.arange(max(q.zmin, -EP) + 0.3, q.zmax - 0.29, 1.0)
    g3 = np.array(np.meshgrid(xs, ys, zs)).reshape(3, -1).T
    if len(g3) and (so.contains(g3).any() or pr.contains(g3).any()):
        pts_c.append(ref)
ctrl(not pts_c, 'aucun composant ne touche le socle ni le porte-pointes (boîtes 3D)' if not pts_c else
     'composant(s) qui touchent une pièce (boîtes 3D) : ' + ', '.join(pts_c))
# le dessus du capot, vu d'en haut : entonnoirs ouverts, braille au complet, chiffres présents
ca = maillages['banc-capot.stl']
pas = 0.2
gx, gy = np.meshgrid(np.arange(JX0, JX1, pas), np.arange(JY0, JY1, pas))
orig = np.c_[gx.ravel(), gy.ravel(), np.full(gx.size, ZC1 + 5)]
hz = np.full(gx.size, np.nan)
for i in range(0, len(orig), 20000):                    # par paquets : moins de mémoire
    loc, idx, _ = ca.ray.intersects_location(orig[i:i + 20000], np.tile([0, 0, -1], (len(orig[i:i + 20000]), 1)), multiple_hits=False)
    hz[i + idx] = loc[:, 2]
hz = hz.reshape(gx.shape)
def pix(x, y):
    return int(round((y - JY0) / pas)), int(round((x - JX0) / pas))
ouverts = sum(np.isnan(hz[pix(p['fx'], p['fy'])]) for p in points)
ctrl(ouverts == len(points), f"{ouverts} entonnoir(s) ouvert(s) jusqu'à leur borne sur {len(points)}")
haut = np.nan_to_num(hz, nan=-99) > ZC1 + 0.3
etiq, _ = ndimage.label(haut)
bons = 0
for p in points:
    ok_b = True
    if AVEC_BRAILLE:
        n_att, cadre = nb_points_braille[p['nom']]
        x0, y0, x1, y1 = cadre.bounds
        (i0, j0), (i1, j1) = pix(x0 - 0.3, y0 - 0.3), pix(x1 + 0.3, y1 + 0.3)
        ok_b = len(set(np.unique(etiq[i0:i1 + 1, j0:j1 + 1])) - {0}) == n_att
    ok_t = True
    for c in p['cadres_relief']:
        x0, y0, x1, y1 = c.bounds
        (i0, j0), (i1, j1) = pix(x0, y0), pix(x1, y1)
        ok_t = ok_t and haut[i0:i1 + 1, j0:j1 + 1].any()
    bons += ok_b and ok_t
ctrl(bons == len(points), ("braille complet (chaque point à sa place, bien séparé), " if AVEC_BRAILLE else '')
     + f"numéro et nom du signal en relief pour {bons} borne(s) sur {len(points)}")
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.figure(figsize=(9, 9 * (JY1 - JY0) / (JX1 - JX0)))
plt.imshow(np.nan_to_num(hz, nan=ZC0 - 1), origin='lower', cmap='gray', extent=[JX0, JX1, JY0, JY1], vmin=ZC1 - 1.5, vmax=ZC1 + 0.8)
for p in points:
    plt.plot(p['x'], p['y'], 'r+', ms=6)
plt.title(f"Capot du banc vu de dessus (en rouge : les pointes, dessous) — {CARTE.nom}", fontsize=9)
plt.savefig(os.path.join(SORTIE, 'banc-capot-vu-de-dessus.png'), dpi=110, bbox_inches='tight')
plt.close()

# ---------- 8. notice
RECESS = VS['tete_hauteur_mm'] + 0.3
besoin = ZC1 - (ZS0 + RECESS) + VS['depasse_pour_ecrou_mm']
LONG_VIS = next((l for l in VS['longueurs_mm'] if l >= besoin), None)
if LONG_VIS is None:
    avert.append(f"vis de {mm(besoin)} mm au moins : plus longue que les longueurs prévues")
ext = {n: maillages[n].extents for n in pieces}
lignes = [f"Banc de test à pointes — {CARTE.nom}", '', f"Fait par la chaîne puzzle le {time.strftime('%d/%m/%Y')}.",
          "Pour mesurer toutes les sorties sans viser les pastilles : chaque sortie arrive sur une borne, au fond d'un entonnoir, "
          "avec son numéro et le nom du signal en lettres en relief" + (", et le numéro en braille" if AVEC_BRAILLE else '') + ". "
          "Les numéros sont ceux du plan de test (TP1 = borne 1…).", '',
          '== À fabriquer ==',
          f"- La carte du banc, chez JLCPCB : fabrication-carte-banc/ (Gerber et perçages), {mm(JX1 - JX0)} × {mm(JY1 - JY0)} mm, 2 couches, "
          "sans composant posé par l'usine.",
          f"- banc-socle.stl : {mm(ext['banc-socle.stl'][0])} × {mm(ext['banc-socle.stl'][1])} × {mm(ext['banc-socle.stl'][2])} mm, posé à plat.",
          f"- banc-porte-pointes.stl : {mm(ext['banc-porte-pointes.stl'][2])} mm d'épaisseur, posé à plat.",
          f"- banc-capot.stl : {mm(ext['banc-capot.stl'][2])} mm d'épaisseur (braille compris), posé face sans braille contre le plateau. "
          f"Couche de {mm(B['couche_impression_mm'])} mm. Le coin coupé est en haut à gauche, comme sur la maquette.", '',
          '== À acheter ==',
          f"- {len(points)} pointes à ressort {P['modele']} (corps ⌀ {mm(P['diametre_corps_mm'])} mm, longueur {mm(L)} mm), plus quelques-unes d'avance.",
          f"- 4 vis M3 × {LONG_VIS or '?'} mm à tête hexagonale (ISO 4017) et 4 écrous papillon M3, qui se serrent à la main.", '',
          '== Montage (une fois, avec quelqu\'un qui soude) ==',
          "1. Glisser chaque pointe par-dessous dans le porte-pointes, puis dans le trou de la carte du banc posée dessus : "
          "le bout de la pointe doit affleurer le dessus de la carte du banc. Souder sur le dessus.",
          "2. Poser le capot sur la carte du banc (le coin coupé du côté du coin coupé de la carte du banc).", '',
          '== Utilisation ==',
          "1. Glisser les 4 vis par-dessous dans le socle : leur tête hexagonale se loge dans le fond, elles ne tournent pas.",
          "2. Poser la carte radio sur le socle, composants vers le haut : les tétons entrent dans ses trous de fixation.",
          "3. Poser par-dessus le porte-pointes, la carte du banc et le capot, enfilés sur les vis.",
          "4. Visser les 4 écrous papillon à la main, jusqu'à ce que le porte-pointes appuie sur les colonnes : les pointes "
          f"sont alors enfoncées de {mm(C)} mm, ni plus ni moins.",
          "5. Mesurer : la pointe du multimètre dans un entonnoir tombe sur la borne. La masse est l'entonnoir carré.",
          f"La prise USB et les prises à fils restent accessibles : rien ne les gêne sur les côtés ({', '.join(t for *_, t in couloirs)}).", '',
          '== Les bornes ==']
for p in points:
    lignes.append(f"- borne {'« masse » (entonnoir carré)' if p['masse'] else p['nom']} : "
                  + (f"couronne du trou {p['ref']}, masse" if p['masse'] else f"sortie {p['ref']}, {p['signal']} (écrit « {nom_court(p['signal'])} »)"))
lignes += ['', '== Hauteurs ==',
           f"- Plus haut composant de la carte : {ref_haut}, {mm(z_haut)} mm ; le porte-pointes passe à {mm(ZH0)} mm au-dessus de la carte.",
           f"- Carte du banc à {mm(ZJ)} mm au-dessus de la carte ; capot de {mm(ZC0)} à {mm(ZC1)} mm.",
           f"- Sous la carte : {mm(SOUS)} mm (les pattes dépassent de {mm(K.pattes)} mm) ; {len(appuis)} appui(s) sous les sorties, en plus des tétons.",
           '', '== Contrôles faits sur le modèle ==', *controles]
if avert:
    lignes += ['', '== À savoir ==', *['- ' + a for a in avert]]
lignes += ['', "Rien n'est encore fabriqué : les cotes des pointes viennent de fiches de vendeurs. Les mesurer à la réception, et "
           "corriger « pointe » dans banc_test.json si elles diffèrent, puis relancer cette étape."]
open(os.path.join(SORTIE, 'banc-test.txt'), 'w', encoding='utf-8').write('\n'.join(lignes) + '\n')
print('\n'.join(lignes))
sys.exit(1 if nb_ko else 0)
