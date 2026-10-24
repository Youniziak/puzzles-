"""Chaîne puzzle, étape 5 — « boîtier d'essai » : un boîtier à imprimer en 3D, fabriqué à partir de la carte.
L'outil est YAPP_Box (pour OpenSCAD, licence MIT, https://github.com/mrWheel/YAPP_Box). Ce script ne dessine rien
lui-même : il lit la carte KiCad et les modèles 3D des composants, et écrit les réglages de YAPP_Box :
  - la taille : la carte, les pattes sous la carte, le plus haut composant ;
  - une ouverture dans la paroi pour chaque prise déclarée dans bloc.json (« boitier » → « ouvertures »), à la taille
    de la prise mesurée sur son modèle 3D, ou de la fiche qu'on y branche si elle est plus grande ;
  - un bouton imprimé dans le dessus pour chaque bouton déclaré (« dessus », type « bouton »), rond ou carré pour les
    reconnaître au toucher, et un trou pour chaque lumière ;
  - un passage de fils dans la paroi la plus proche de chaque prise à fils (« fils ») ;
  - le nom de chaque ouverture et bouton, en lettres creusées dans le dessus ;
  - des plots de maintien : sur les trous de fixation de la carte s'il y en a ; sinon, des plots qui pincent la carte
    entre le fond et le dessus, là où il n'y a ni composant ni patte ;
  - deux crochets pour fermer le dessus, sur des parois sans ouverture.
OpenSCAD fabrique ensuite les pièces, et le script les contrôle : le dessus est remis en place par le calcul, puis
on vérifie que les ouvertures et les trous traversent, qu'aucun composant ni la carte ne rentre dans une paroi, et que
les plots touchent la carte.
Réglages : bibliotheque/regles/boitier.json. Sorties dans dossier_projet/boitier/ : boitier.scad, boitier-fond.stl,
boitier-dessus.stl (le dessus et ses boutons), boitier.txt (notice et contrôles).
Usage : python3 boitier.py cartes/ma-carte.json dossier_projet/carte.kicad_pcb chemin/YAPP_Box"""
import json, os, re, subprocess, sys, time
import cadquery as cq
import numpy as np
import pcbnew
import trimesh
from shapely.geometry import Point, box
from shapely.ops import unary_union
from shapely.prepared import prep
from description import Carte
from modeles3d import Carte3D

CARTE = Carte(sys.argv[1])
PCB, YAPP = os.path.abspath(sys.argv[2]), os.path.abspath(sys.argv[3])
GEN = os.path.join(YAPP, 'YAPPgenerator_v3.scad')
if not os.path.exists(GEN):
    sys.exit(f"YAPP_Box introuvable : {GEN} (installer-ubuntu.sh le télécharge)")
R = json.load(open(os.path.join(CARTE.bibliotheque, 'regles', 'boitier.json'), encoding='utf-8'))
SORTIE = os.path.join(os.path.dirname(PCB), 'boitier')
os.makedirs(SORTIE, exist_ok=True)
avert, controles = [], []
mm = lambda v: str(round(v, 1)).replace('.', ',')

# ---------- la carte et ses composants (modèles 3D), dans le repère commun : origine au coin bas-gauche de la carte,
# y vers le haut, z = 0 sur le dessus de la carte (module modeles3d, partagé avec le banc de test)
K = Carte3D(CARTE, PCB)
W, H, EP, contour = K.W, K.H, K.EP, K.contour
formes, boites, sans_3d = K.formes, K.boites, K.sans_3d
emprise_dessus, emprise_dessous = K.emprise_dessus, K.emprise_dessous
trous_fixation = [(xy_, d) for _, xy_, d, _ in K.trous]
for ref in K.dessous:
    avert.append(f"{ref} est sous la carte : sa hauteur n'est pas prise en compte (cas pas encore géré)")
if sans_3d:
    avert.append('sans modèle 3D (hauteur inconnue, non contrôlés) : ' + ', '.join(sans_3d))

# ---------- hauteurs
pattes = max([0] + [-q.zmin - EP for q in boites.values()])
SOUS = max(R['sous_la_carte_min_mm'], pattes + R['jeu_sous_les_pattes_mm'])
PLUS_HAUT = max(q.zmax for q in boites.values())
REF_HAUT = max(boites, key=lambda r: boites[r].zmax)
PAROI, MARGE, FOND, TOIT = R['paroi_mm'], R['marge_autour_carte_mm'], R['fond_mm'], R['dessus_mm']

# ---------- éléments déclarés par les blocs
FACES = {   # côté de la carte → face YAPP, axe perpendiculaire, sens, axe le long de la face
    'gauche': ('Back', 0, -1, 1), 'droite': ('Front', 0, 1, 1), 'bas': ('Left', 1, -1, 0), 'haut': ('Right', 1, 1, 0)}
COTE = {'gauche': 'gauche', 'droite': 'droit', 'bas': 'bas', 'haut': 'haut'}
def face_proche(q):
    d = {'gauche': q.xmin, 'droite': W - q.xmax, 'bas': q.ymin, 'haut': H - q.ymax}
    f = min(d, key=d.get)
    return f, d[f]

declares = {'ouvertures': [], 'dessus': [], 'fils': []}
for b in CARTE.blocs:
    for genre, liste in b.bloc.get('boitier', {}).items():
        for e in liste:
            ref = CARTE.repere(b, e['ref'])
            if ref not in boites:
                avert.append(f"{ref} (bloc {b.id}, {genre}) : pas de modèle 3D sur la carte, ignoré")
                continue
            declares[genre].append(dict(e, ref=ref))
if not any(declares.values()):
    avert.append("aucun bloc ne déclare d'ouverture, de bouton ni de fil (« boitier » dans bloc.json)")

def section(ref, face):
    """Coupe du modèle 3D près de son extrémité côté paroi : la bouche de la prise (coquille USB, filetage SMA…)."""
    q, (_, axe, sens, _) = boites[ref], FACES[face]
    ext = [q.xmin, q.ymin][axe] if sens < 0 else [q.xmax, q.ymax][axe]
    a0 = ext + 0.2 if sens < 0 else ext - 1.0
    tranche = cq.Solid.makeBox(*([0.8, 400, 400] if axe == 0 else [400, 0.8, 400]),
                               cq.Vector(*([a0, -200, -200] if axe == 0 else [-200, a0, -200])))
    try:
        s = formes[ref].intersect(tranche).BoundingBox()
        le_long = (s.ymin, s.ymax) if axe == 0 else (s.xmin, s.xmax)
        if le_long[1] - le_long[0] > 0.1:
            return le_long, (s.zmin, s.zmax)
    except Exception:
        pass
    return ((q.ymin, q.ymax) if axe == 0 else (q.xmin, q.xmax)), (q.zmin, q.zmax)

J = R['ouvertures']['jeu_mm']
ouvertures = []      # face, centre le long, centre z, largeur, hauteur, rond, texte, ref, genre
for o in declares['ouvertures']:
    face, dist = face_proche(boites[o['ref']])
    if dist > 3:
        avert.append(f"{o['ref']} ({o['texte']}) est à {mm(dist)} mm du bord : l'ouverture est faite quand même, côté {COTE[face]}")
    (a0, a1), (z0, z1) = section(o['ref'], face)
    fw, fh = o.get('fiche_mm', [0, 0])
    w, h = max(a1 - a0, fw) + 2 * J, max(z1 - z0, fh) + 2 * J
    rond = o.get('forme') == 'rond'
    if rond:
        w = h = max(w, h)
    ouvertures.append(dict(face=face, a=(a0 + a1) / 2, z=(z0 + z1) / 2, w=w, h=h, rond=rond, texte=o['texte'], ref=o['ref'], genre='prise'))

def chevauche(face, a, z, w, h, sauf=None):
    return any(o is not sauf and o['face'] == face and abs(o['a'] - a) < (o['w'] + w) / 2 + 1 and abs(o['z'] - z) < (o['h'] + h) / 2 + 1
               for o in ouvertures)

PF = R['passages_fils']
for fl in declares['fils']:
    q = boites[fl['ref']]
    face, _ = face_proche(q)
    axe_long = FACES[face][3]
    a = (q.xmin + q.xmax) / 2 if axe_long == 0 else (q.ymin + q.ymax) / 2
    longueur = W if axe_long == 0 else H
    z = PF['hauteur_mm'] / 2 + 0.5
    place = None
    for d in sorted(np.arange(-PF['glissement_max_mm'], PF['glissement_max_mm'] + 0.01, 0.5), key=abs):
        a2 = a + d
        if PF['largeur_mm'] / 2 + 2 <= a2 <= longueur - PF['largeur_mm'] / 2 - 2 and not chevauche(face, a2, z, PF['largeur_mm'], PF['hauteur_mm']):
            place = a2
            break
    if place is None:
        avert.append(f"pas de place pour le passage de fils de {fl['ref']} ({fl['texte']}) côté {COTE[face]}")
        continue
    ouvertures.append(dict(face=face, a=place, z=z, w=PF['largeur_mm'], h=PF['hauteur_mm'], rond=False,
                           texte=fl['texte'], ref=fl['ref'], genre='fils'))

# ---------- taille du boîtier : le plus haut composant, et les ouvertures doivent tenir entières dans la paroi
HAUT_OUV = max([o['z'] + o['h'] / 2 + 1.0 for o in ouvertures] + [0])
DESSUS_INT = max(PLUS_HAUT + R['au_dessus_du_plus_haut_mm'], HAUT_OUV)
if HAUT_OUV > PLUS_HAUT + R['au_dessus_du_plus_haut_mm']:
    avert.append(f"le boîtier est rehaussé à {mm(DESSUS_INT)} mm au-dessus de la carte pour que l'ouverture la plus haute tienne dans la paroi")
for o in ouvertures:
    if o['z'] - o['h'] / 2 < -(SOUS + EP) + 0.5:
        avert.append(f"l'ouverture {o['ref']} « {o['texte']} » descend presque jusqu'au fond")
BASE_PAROI = SOUS + EP + R['jonction_au_dessus_carte_mm']
COUV_PAROI = max(SOUS + EP + DESSUS_INT - BASE_PAROI, R['nervure_mm'] + 1)
L_BOITE, l_BOITE = W + 2 * MARGE + 2 * PAROI, H + 2 * MARGE + 2 * PAROI
H_BOITE = FOND + BASE_PAROI + COUV_PAROI + TOIT
OX = OY = PAROI + MARGE                      # carte → boîtier
OZ = FOND + SOUS + EP                        # z du dessus de la carte dans le boîtier

BT = R['boutons']
dessus = []           # x, y, rayon d'exclusion, ligne YAPP, texte, ref, genre
for e in declares['dessus']:
    q = boites[e['ref']]
    x, y = (q.xmin + q.xmax) / 2, (q.ymin + q.ymax) / 2
    if e.get('type') == 'bouton':
        if e.get('forme') == 'carre':
            c = BT['carre_cote_mm']
            yapp = f"[{x:.3f}, {y:.3f}, {c}, {c}, 0, {BT['depasse_du_dessus_mm']}, {q.zmax:.3f}, {BT['course_mm']}, {BT['tige_diametre_mm']}, undef, yappRectangle]"
            r_ex = c * 0.71
        else:
            d = BT['rond_diametre_mm']
            yapp = f"[{x:.3f}, {y:.3f}, 0, 0, {d / 2}, {BT['depasse_du_dessus_mm']}, {q.zmax:.3f}, {BT['course_mm']}, {BT['tige_diametre_mm']}, undef, yappCircle]"
            r_ex = d / 2
        dessus.append(dict(x=x, y=y, r=r_ex + 1, yapp=yapp, texte=e['texte'], ref=e['ref'], genre='bouton ' + ('carré' if e.get('forme') == 'carre' else 'rond')))
    else:
        d = R['trou_lumiere_mm']
        dessus.append(dict(x=x, y=y, r=d / 2 + 0.5, yapp=f"[{x:.3f}, {y:.3f}, 0, 0, {d / 2}, yappCircle, 0, 0, yappCoordPCB, yappCenter]",
                           texte=e['texte'], ref=e['ref'], genre='trou'))

# ---------- plots de maintien
PL = R['plots_de_maintien']
rp = PL['diametre_mm'] / 2
# un téton dans chaque trou de fixation ; à chaque coin sans trou proche, un plot qui pince la carte (fond et dessus)
plots = [(x, y, 'teton') for (x, y), _ in trous_fixation]
genant = unary_union([g.buffer(PL['marge_composants_mm'] + rp) for g in emprise_dessus + emprise_dessous])
genant = unary_union([genant] + [Point(e['x'], e['y']).buffer(e['r'] + rp) for e in dessus]
                     + [Point(x, y).buffer(8 + rp) for (x, y), _ in trous_fixation])
libre = prep(contour.buffer(-(PL['marge_bord_mm'] + rp)).difference(genant))
grille = [(float(x), float(y)) for x in np.arange(0, W, 0.5) for y in np.arange(0, H, 0.5)]
R_CHERCHE = PL['recherche_le_long_du_bord_mm']
for cx, cy in ((0, 0), (W, 0), (0, H), (W, H)):
    if any(np.hypot(x - cx, y - cy) <= R_CHERCHE for (x, y), _ in trous_fixation):
        continue
    proches = sorted((np.hypot(x - cx, y - cy), (x, y)) for x, y in grille if np.hypot(x - cx, y - cy) <= R_CHERCHE)
    libre_ici = next((pt for _, pt in proches if libre.contains(Point(pt))), None)
    if libre_ici:
        plots.append((*libre_ici, 'pince'))
if len(plots) < 3:
    avert.append(f"seulement {len(plots)} point(s) de maintien ont trouvé de la place : la carte risque de bouger")
nb_tetons, nb_pinces = sum(p[2] == 'teton' for p in plots), sum(p[2] == 'pince' for p in plots)
# plots comptés depuis le coin arrière-gauche de la carte (réglage par défaut de YAPP) ; pour pincer : creux, sans arrondi
plots_yapp = [f"[{x:.3f}, {y:.3f}, yappBoth, {'yappHole, yappNoFillet' if g == 'pince' else 'yappPin'}]" for x, y, g in plots]

# ---------- étiquettes creusées dans le dessus
ET = R['etiquettes']
T = ET['taille_mm']
zone_dessus = box(-MARGE + 1, -MARGE + 1, W + MARGE - 1, H + MARGE - 1)
occupe = [Point(e['x'], e['y']).buffer(e['r']) for e in dessus]
etiquettes = []
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
_police = FontProperties(family=ET['police'].split(':')[0], weight='bold' if 'Bold' in ET['police'] else 'normal')
_cap = TextPath((0, 0), 'H', size=1, prop=_police).get_extents().height
def largeur(texte):
    """Largeur réelle du mot dans la police d'OpenSCAD, où « taille » est la hauteur des capitales."""
    return TextPath((0, 0), texte, size=T / _cap, prop=_police).get_extents().width

def poser(texte, candidats):
    lw = largeur(texte)
    for cx, cy in candidats:
        r = box(cx - lw / 2, cy - T / 2, cx + lw / 2, cy + T / 2)
        if zone_dessus.contains(r) and not any(r.buffer(ET['ecart_mm'] - 0.05).intersects(o) for o in occupe):
            occupe.append(r)
            etiquettes.append((cx, cy, texte))
            return True
    avert.append(f"pas de place pour écrire « {texte} » sur le dessus")
    return False

for e in dessus:
    g = e['r'] + ET['ecart_mm'] + T / 2
    lw = largeur(e['texte'])
    poser(e['texte'], [(e['x'], e['y'] - g), (e['x'], e['y'] + g), (e['x'] + e['r'] + ET['ecart_mm'] + lw / 2, e['y']),
                       (e['x'] - e['r'] - ET['ecart_mm'] - lw / 2, e['y'])])
for o in ouvertures:
    _, axe, sens, axe_long = FACES[o['face']]
    cands = []
    lw = largeur(o['texte'])
    for retrait in np.arange(1.5, 25, 1.0):          # distance entre le bord de la carte et l'étiquette
        for glisse in np.arange(-15, 15.01, 1.0):
            if axe_long == 0:
                cands.append((np.hypot(glisse, retrait - 1.5), (o['a'] + glisse, retrait + T / 2 if sens < 0 else H - retrait - T / 2)))
            else:
                cands.append((np.hypot(glisse, retrait - 1.5), (retrait + lw / 2 if sens < 0 else W - retrait - lw / 2, o['a'] + glisse)))
    cands = [c for _, c in sorted(cands, key=lambda c: c[0])]
    poser(o['texte'], cands)

# ---------- crochets de fermeture, sur deux faces opposées sans ouverture au milieu
crochets = []
def place_crochet(face):
    longueur = W if FACES[face][3] == 0 else H
    for d in sorted(np.arange(-longueur / 2 + 10, longueur / 2 - 9.99, 0.5), key=abs):
        if not chevauche(face, longueur / 2 + d, 0, 8, 100):
            return longueur / 2 + d + (OX if FACES[face][3] == 0 else OY)
    return None
for f1, f2 in (('bas', 'haut'), ('gauche', 'droite')):
    p1, p2 = place_crochet(f1), place_crochet(f2)
    if p1 is not None and p2 is not None:
        crochets = [f"[{p1:.3f}, 6, yapp{FACES[f1][0]}, yappCenter]", f"[{p2:.3f}, 6, yapp{FACES[f2][0]}, yappCenter]"]
        break
if not crochets:
    avert.append("pas de place libre pour les crochets : le dessus tient seulement par la nervure (serrage)")

# ---------- fichier OpenSCAD
def liste(lignes):
    if not lignes:
        return '[]'
    sortie = []
    for i, l in enumerate(lignes):
        code, _, note = l.partition('//')
        sortie.append(code.rstrip() + (',' if i < len(lignes) - 1 else '') + (f'   //{note}' if note else ''))
    return '[\n  ' + '\n  '.join(sortie) + '\n]'
coupes = {f: [] for f in ('Back', 'Front', 'Left', 'Right')}
for o in ouvertures:
    y = FACES[o['face']][0]
    if o['rond']:
        coupes[y].append(f"[{o['a']:.3f}, {o['z']:.3f}, 0, 0, {o['w'] / 2:.3f}, yappCircle, 0, 0, yappCoordPCB, yappCenter]   // {o['ref']} {o['texte']}")
    else:
        coupes[y].append(f"[{o['a']:.3f}, {o['z']:.3f}, {o['w']:.3f}, {o['h']:.3f}, {R['ouvertures']['rayon_coins_mm']}, yappRoundedRect, 0, 0, yappCoordPCB, yappCenter]   // {o['ref']} {o['texte']}")
lignes_et = [f"[{x + OX:.3f}, {y + OY:.3f}, 0, {ET['profondeur_mm']}, yappLid, \"{ET['police']}\", {T}, \"{t}\", 0, yappTextLeftToRight, "
             f"yappTextHAlignCenter, yappTextVAlignCenter, 1.0]" for x, y, t in etiquettes]   # YAPP : depuis le coin du boîtier
scad = f"""// Boîtier d'essai de « {CARTE.nom} », écrit par la chaîne puzzle (boitier.py). Ne pas modifier à la main :
// changer bibliotheque/regles/boitier.json ou « boitier » dans bloc.json, puis relancer.
// Outil : YAPP_Box {R['yapp']['version']} (licence MIT, {R['yapp']['depot']}).
include <{GEN}>

printBaseShell = true; printLidShell = true; printSwitchExtenders = true; printDisplayClips = false;
shiftLid = 10; showSideBySide = true; onLidGap = 0;
pcbLength = {W:.3f}; pcbWidth = {H:.3f}; pcbThickness = {EP:.3f};
standoffHeight = {SOUS:.3f}; standoffDiameter = {PL['diametre_mm']}; standoffPinDiameter = {min([d for _, d in trous_fixation] + [2.8]) - 0.4:.3f}; standoffHoleSlack = 0.4;
pcb = [["Main", pcbLength, pcbWidth, 0, 0, pcbThickness, standoffHeight, standoffDiameter, standoffPinDiameter, standoffHoleSlack]];
paddingFront = {MARGE}; paddingBack = {MARGE}; paddingRight = {MARGE}; paddingLeft = {MARGE};
wallThickness = {PAROI}; basePlaneThickness = {FOND}; lidPlaneThickness = {TOIT};
baseWallHeight = {BASE_PAROI:.3f}; lidWallHeight = {COUV_PAROI:.3f};
ridgeHeight = {R['nervure_mm']}; ridgeSlack = {R['jeu_nervure_mm']}; ridgeGap = 0.5; roundRadius = {R['arrondi_boite_mm']}; boxType = 0;
printerLayerHeight = {R['couche_impression_mm']}; renderQuality = {R['qualite_rendu']}; previewQuality = 5;
pcbStands = {liste(plots_yapp)};
connectors = [];
cutoutsBase = [];
cutoutsLid = {liste([e['yapp'] + f"   // {e['ref']} {e['texte']}" for e in dessus if e['genre'] == 'trou'])};
cutoutsFront = {liste(coupes['Front'])};
cutoutsBack = {liste(coupes['Back'])};
cutoutsLeft = {liste(coupes['Left'])};
cutoutsRight = {liste(coupes['Right'])};
snapJoins = {liste(crochets)};
lightTubes = [];
pushButtons = {liste([e['yapp'] + f"   // {e['ref']} {e['texte']}" for e in dessus if e['genre'].startswith('bouton')])};
labelsPlane = {liste(lignes_et)};
YAPPgenerate();
"""
SCAD = os.path.join(SORTIE, 'boitier.scad')
open(SCAD, 'w', encoding='utf-8').write(scad)
TOUT = os.path.join(SORTIE, 'boitier-tout.stl')
r = subprocess.run(['openscad', '-o', TOUT, SCAD], capture_output=True, text=True)
messages = [l for l in r.stderr.splitlines() if re.search(r'WARNING|ERROR', l) and 'CGAL Cache' not in l]
if r.returncode or not os.path.exists(TOUT):
    sys.exit('OpenSCAD a échoué :\n' + '\n'.join(r.stderr.splitlines()[-15:]))
for l in messages[:8]:   # avertissements d'OpenSCAD, tels quels
    avert.append('OpenSCAD : ' + l.strip()[:160])

# ---------- pièces : le fond, le dessus (remis en place par le calcul), les boutons
tout = trimesh.load(TOUT)
corps = tout.split(only_watertight=False)
fond_m = max([c for c in corps if c.bounds[1][1] < l_BOITE + 2], key=lambda c: abs(c.volume))
dessus_m = max([c for c in corps if c.bounds[0][1] > l_BOITE], key=lambda c: abs(c.volume))
boutons_m = [c for c in corps if c is not fond_m and c is not dessus_m]
fond_m.export(os.path.join(SORTIE, 'boitier-fond.stl'))
trimesh.util.concatenate([dessus_m] + boutons_m).export(os.path.join(SORTIE, 'boitier-dessus.stl'))
os.remove(TOUT)
# YAPP pose le dessus à l'envers à côté du fond : y' = 2 (5 + largeur + décalage/2) − y, z' = −(z − hauteur)
Tdec = 2 * (5 + l_BOITE + 10 / 2)
M = np.diag([1.0, -1.0, -1.0, 1.0]); M[1, 3], M[2, 3] = Tdec, H_BOITE
dessus_place = dessus_m.copy(); dessus_place.apply_transform(M)
etanches = fond_m.is_watertight and dessus_m.is_watertight and all(c.is_watertight for c in boutons_m)
controles.append(('✓' if etanches else '✗') + f" pièces fermées (prêtes à imprimer) : fond {'oui' if fond_m.is_watertight else 'NON'}, dessus {'oui' if dessus_m.is_watertight else 'NON'} ; {len(boutons_m)} pièce(s) de bouton")

coque = trimesh.util.concatenate([fond_m, dessus_place])
def traverse(origine, direction, a, b, axe):
    """Le rayon traverse-t-il la paroi (entre a et b sur l'axe) sans toucher de matière ?"""
    pts, _, _ = coque.ray.intersects_location([origine], [direction])
    return not any(a - 0.05 <= p[axe] <= b + 0.05 for p in pts)

def en_boite(x, y, z):
    return x + OX, y + OY, z + OZ

nb_ko = 0
for o in ouvertures:
    yface, axe, sens, axe_long = FACES[o['face']]
    oks = []
    for da, dz in ((0, 0), (0.35, 0), (-0.35, 0), (0, 0.35), (0, -0.35)):
        a, z = o['a'] + da * o['w'], o['z'] + dz * o['h']
        if axe == 0:
            x0 = -5 if sens < 0 else L_BOITE + 5
            org = (x0, en_boite(0, a, 0)[1], en_boite(0, 0, z)[2])
            oks.append(traverse(org, (-sens, 0, 0), *((0, PAROI) if sens < 0 else (L_BOITE - PAROI, L_BOITE)), 0))
        else:
            y0 = -5 if sens < 0 else l_BOITE + 5
            org = (en_boite(a, 0, 0)[0], y0, en_boite(0, 0, z)[2])
            oks.append(traverse(org, (0, -sens, 0), *((0, PAROI) if sens < 0 else (l_BOITE - PAROI, l_BOITE)), 1))
    nb_ko += not all(oks)
    controles.append(f"{'✓' if all(oks) else '✗'} {o['genre']} {o['ref']} « {o['texte']} », côté {COTE[o['face']]} de la carte : "
                     f"{'traverse la paroi' if all(oks) else f'bouchée ({oks.count(False)} point(s) sur 5)'} "
                     f"({'⌀ ' + mm(o['w']) if o['rond'] else mm(o['w']) + ' × ' + mm(o['h'])} mm)")
for e in dessus:
    x, y, _ = en_boite(e['x'], e['y'], 0)
    ok = traverse((x, y, H_BOITE + 5), (0, 0, -1), H_BOITE - TOIT, H_BOITE, 2)
    nb_ko += not ok
    controles.append(f"{'✓' if ok else '✗'} {e['genre']} {e['ref']} « {e['texte']} » : {'passe à travers le dessus' if ok else 'le dessus est plein à cet endroit'}")

# collisions : des points dans chaque composant (sa boîte 3D, réduite de 0,3 mm) ne doivent être dans aucune paroi
def points(q, pas=1.0):
    xs = np.arange(q.xmin + 0.3, q.xmax - 0.29, pas); ys = np.arange(q.ymin + 0.3, q.ymax - 0.29, pas); zs = np.arange(q.zmin + 0.3, q.zmax - 0.29, pas)
    g = np.array(np.meshgrid(xs, ys, zs)).reshape(3, -1).T
    return g + np.array([OX, OY, OZ]) if len(g) else g
touches = []
for ref, q in boites.items():
    p = points(q)
    if len(p) and (fond_m.contains(p).any() or dessus_place.contains(p).any()):
        touches.append(ref)
nb_ko += bool(touches)
controles.append('✓ aucun composant ne rentre dans une paroi (contrôle sur leur boîte 3D)' if not touches else
                 '✗ composant(s) dans une paroi ou un plot (contrôle sur leur boîte 3D, à regarder) : ' + ', '.join(touches))
gx, gy = np.meshgrid(np.arange(0.5, W, 1.5), np.arange(0.5, H, 1.5))
dans = [(x, y) for x, y in zip(gx.ravel(), gy.ravel()) if contour.buffer(-0.3).contains(Point(x, y))
        and all(np.hypot(x - tx, y - ty) > d / 2 + 0.2 for (tx, ty), d in trous_fixation)]   # les tétons passent dans les trous
p = np.array([en_boite(x, y, -EP / 2) for x, y in dans])
dedans = fond_m.contains(p) | dessus_place.contains(p)
ok = not dedans.any()
nb_ko += not ok
controles.append(f"{'✓' if ok else '✗'} la carte tient dans le boîtier sans toucher les parois"
                 + ('' if ok else ' ; points de la carte dans une pièce : ' + ', '.join([f'({mm(x)} ; {mm(y)})' for (x, y), k in zip(dans, dedans) if k][:6])))
r_anneau = ((min([d for _, d in trous_fixation] + [2.8]) - 0.4 + 0.4) / 2 + rp) / 2      # milieu de l'anneau du plot
def ecart(maillage, x, y, sens):
    bx, by, bz = en_boite(x, y, -EP / 2)
    ds = []
    for ax, ay in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        pts = maillage.ray.intersects_location([(bx + ax * r_anneau, by + ay * r_anneau, bz)], [(0, 0, sens)])[0]
        if len(pts):
            ds.append((min(p[2] for p in pts) - bz if sens > 0 else bz - max(p[2] for p in pts)) - EP / 2)
    return float(np.median(ds)) if ds else None
for x, y, genre in plots:
    d_bas, d_haut = ecart(fond_m, x, y, -1), ecart(dessus_place, x, y, 1)
    ok_b = d_bas is not None and abs(d_bas) < 0.35
    ok_h = d_haut is not None and abs(d_haut) < 0.35
    nb_ko += not (ok_b and ok_h)
    txt_b = 'touché' if ok_b else 'écart ' + (mm(d_bas) if d_bas is not None else '?') + ' mm'
    txt_h = 'touché' if ok_h else 'écart ' + (mm(d_haut) if d_haut is not None else '?') + ' mm'
    controles.append(f"{'✓' if ok_b and ok_h else '✗'} {'téton dans un trou' if genre == 'teton' else 'plot qui pince'} en "
                     f"({mm(x)} ; {mm(y)}) mm : dessous de la carte {txt_b}, dessus de la carte {txt_h}")

# lettres : on regarde le dessus remis en place, vu d'en haut (une hauteur tous les 0,2 mm)
pas = 0.2
gx, gy = np.meshgrid(np.arange(0, L_BOITE, pas), np.arange(0, l_BOITE, pas))
orig = np.c_[gx.ravel(), gy.ravel(), np.full(gx.size, H_BOITE + 5)]
loc, idx, _ = dessus_place.ray.intersects_location(orig, np.tile([0, 0, -1], (len(orig), 1)), multiple_hits=False)
hz = np.full(gx.size, np.nan); hz[idx] = loc[:, 2]; hz = hz.reshape(gx.shape)
bord = R['arrondi_boite_mm'] + 0.5          # l'arrondi du bord passe aussi par cette hauteur : on le laisse de côté
interieur = (gx > bord) & (gx < L_BOITE - bord) & (gy > bord) & (gy < l_BOITE - bord)
creux = (np.abs(hz - (H_BOITE - ET['profondeur_mm'])) < 0.06) & interieur
dans_un_cadre = np.zeros_like(creux)
ok_l = True
for x, y, texte in etiquettes:
    lw = largeur(texte)
    cadre = (np.abs(gx - (x + OX)) <= lw / 2 + 0.6) & (np.abs(gy - (y + OY)) <= T / 2 + 0.6)
    dans_un_cadre |= cadre
    if creux[cadre].mean() < 0.08:
        ok_l = False
        avert.append(f"« {texte} » n'est pas creusé là où il était prévu")
hors = int((creux & ~dans_un_cadre).sum())
ok_l = ok_l and hors < 0.005 * max(1, creux.sum())
nb_ko += not ok_l
controles.append(f"{'✓' if ok_l else '✗'} {len(etiquettes)} nom(s) creusé(s) dans le dessus, chacun à sa place, sans déborder sur un voisin"
                 + ('' if ok_l else f" ({hors} point(s) de lettre hors de leur cadre)"))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.figure(figsize=(9, 7.5))
plt.imshow(hz, origin='lower', cmap='gray', extent=[0, L_BOITE, 0, l_BOITE], vmin=H_BOITE - 1.2, vmax=H_BOITE)
plt.title(f"Dessus du boîtier, vu de dessus : creux en sombre — {CARTE.nom}")
plt.xlabel('mm'); plt.ylabel('mm')
plt.savefig(os.path.join(SORTIE, 'boitier-dessus-vu-de-dessus.png'), dpi=110, bbox_inches='tight')
plt.close()

# ---------- notice
ext_f, ext_d = fond_m.extents, dessus_m.extents
noms_face = {'gauche': 'gauche', 'droite': 'droit', 'bas': 'du bas', 'haut': 'du haut'}
notice = [f"Boîtier d'essai — {CARTE.nom}", '',
          f"Fabriqué par YAPP_Box {R['yapp']['version']} (OpenSCAD) à partir de la carte, le {time.strftime('%d/%m/%Y')}.",
          "Les côtés sont ceux de la carte vue de dessus, prise USB vers soi si elle est en bas.", '',
          '== Pièces à imprimer ==',
          f"- boitier-fond.stl : le fond, {mm(ext_f[0])} × {mm(ext_f[1])} × {mm(ext_f[2])} mm, posé à plat.",
          f"- boitier-dessus.stl : le dessus, {mm(ext_d[0])} × {mm(ext_d[1])} × {mm(ext_d[2])} mm, posé face extérieure contre le plateau"
          + (f", et {len(boutons_m)} pièce(s) de bouton à côté." if boutons_m else '.'),
          *(["- Chaque bouton est en deux pièces : le capuchon avec sa tige, et une petite plaque à coller au bout de la tige, "
             "sous le dessus, pour que le bouton ne tombe pas (documentation de YAPP_Box). Le bouton rond et le bouton carré se "
             "reconnaissent au toucher."] if boutons_m else []),
          f"- Couche de {mm(R['couche_impression_mm'])} mm. Les lettres sont creusées de {mm(ET['profondeur_mm'])} mm dans le dessus : elles "
          "sont imprimées contre le plateau, donc sans support. Le braille n'est pas possible sur cette face (il faudrait des points en relief "
          "contre le plateau) : une étiquette braille collée peut le compléter.",
          '- Matière : plastique seulement. Un boîtier en métal couperait l\'antenne WiFi et la radio.', '',
          '== Ce qu\'on trouve au toucher ==']
for o in ouvertures:
    notice.append(f"- côté {noms_face[o['face']]} : {'prise' if o['genre'] == 'prise' else 'passage de fils'} « {o['texte']} » ({o['ref']})"
                  f", {'ronde, ⌀ ' + mm(o['w']) if o['rond'] else mm(o['w']) + ' × ' + mm(o['h'])} mm")
for e in dessus:
    notice.append(f"- sur le dessus : {e['genre']} « {e['texte']} » ({e['ref']}), nom écrit en creux à côté")
notice += ['', '== Maintien de la carte ==']
if nb_tetons:
    notice.append(f"La carte est posée sur {nb_tetons} plot(s) du fond, avec un téton qui entre dans chaque trou de fixation ; "
                  "un plot du dessus appuie sur la carte au même endroit.")
if nb_pinces:
    notice.append(f"{'En plus, aux' if nb_tetons else 'Aux'} coins sans trou, {nb_pinces} plot(s) du fond et autant du dessus "
                  f"(⌀ {mm(PL['diametre_mm'])} mm) pincent la carte, là où il n'y a ni composant ni patte.")
if not trous_fixation:
    notice.append("La carte n'a pas de trou de fixation : en ajouter la tiendrait plus sûrement (« trous_fixation » dans la description de la carte).")
notice.append("Le dessus " + ("se ferme avec deux crochets." if crochets else "tient par la nervure seulement (serrage)."))
notice += ['', '== Hauteurs ==',
           f"- Sous la carte : {mm(SOUS)} mm (les pattes dépassent de {mm(pattes)} mm).",
           f"- Au-dessus de la carte : {mm(DESSUS_INT)} mm (plus haut composant : {REF_HAUT}, {mm(PLUS_HAUT)} mm).",
           "- Pas d'aération : le calcul d'échauffement de l'étape 0 bis suppose une carte à l'air libre. À surveiller au premier essai.",
           '', '== Contrôles faits sur le modèle ==', *controles]
if avert:
    notice += ['', '== À savoir ==', *['- ' + a for a in avert]]
notice += ['', "Étiquettes en braille : etiquettes-braille.txt, une par ligne, à embosser (par exemple avec une BrailleRAP et son "
           "logiciel AccessBrailleRAP) puis à coller à côté de chaque prise ou bouton."]
notice += ['', "Rien n'est encore imprimé : la première impression dira si les jeux (prises, boutons, nervure) conviennent à l'imprimante."]
open(os.path.join(SORTIE, 'boitier.txt'), 'w', encoding='utf-8').write('\n'.join(notice) + '\n')
# étiquettes à embosser en braille (le dessus imprimé ne peut pas porter de braille en relief) : texte simple, une
# étiquette par ligne, à ouvrir dans AccessBrailleRAP (logiciel de l'embosseuse libre BrailleRAP, qui traduit avec liblouis)
etiq = [f"{o['texte']} : {'prise' if o['genre'] == 'prise' else 'fils'}, côté {noms_face[o['face']]}" for o in ouvertures]
etiq += [f"{e['texte']} : {e['genre']}, sur le dessus" for e in dessus]
open(os.path.join(SORTIE, 'etiquettes-braille.txt'), 'w', encoding='utf-8').write('\n'.join(etiq) + '\n')
print('\n'.join(notice))
sys.exit(1 if nb_ko or not etanches else 0)
