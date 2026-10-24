"""Contrôle indépendant des fichiers de fabrication (Gerber + perçages), sans passer par KiCad.
On redessine le cuivre réellement envoyé à l'usine (bibliothèques libres gerbonara + shapely). On le compare aux
pastilles attendues, calculées à partir des fichiers EasyGerber des blocs et de leur place sur la carte :
  1. chaque réseau forme un seul morceau de cuivre (pas de coupure) ;
  2. aucun morceau de cuivre ne relie deux réseaux différents (pas de court-circuit) ;
  3. l'écart minimal entre cuivres de réseaux différents ;
  4. pas de cuivre dans les zones interdites des blocs (antenne…) ;
  5. la distance du cuivre au bord de la carte ;
  6. les diamètres de perçage ;
  7. l'écart entre les trous et le cuivre d'un autre réseau ;
  8. la couronne de cuivre autour des trous de composants ;
  9. la largeur du cuivre de chaque alimentation par rapport à son courant.
Les seuils viennent du fichier de règles du fabricant. À la fin, un bilan : ce qui est à corriger.
Usage : python3 -I verif_gerber.py cartes/ma-carte.json dossier_gerber/ [règles d'un autre fabricant]"""
import json, math, sys, os, warnings
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collections import defaultdict
from shapely.geometry import Point, LineString, Polygon, box
from shapely.affinity import rotate, translate
from shapely.ops import unary_union
from shapely.strtree import STRtree
from gerbonara import GerberFile, ExcellonFile
from gerbonara.utils import MM
import gerbonara.graphic_primitives as gp
from description import Carte
warnings.filterwarnings('ignore')

CARTE = Carte(sys.argv[1], sys.argv[3] if len(sys.argv) > 3 else None)
FAB = sys.argv[2]
W, H = CARTE.largeur, CARTE.hauteur
REGLES = CARTE.regles
A_CORRIGER = []

def fichier(suffixe):
    # noms de KiCad (…-F_Cu.gtl) ou de KiKit (…-CuTop.gtl) : on se fie à l'extension
    ext = {'F_Cu.gtl': '.gtl', 'B_Cu.gbl': '.gbl', '-PTH.drl': '-PTH.drl', 'NPTH.drl': '-NPTH.drl', 'F_Silkscreen.gto': '.gto'}.get(suffixe, suffixe)
    return os.path.join(FAB, [f for f in os.listdir(FAB) if f.endswith(ext)][0])

def prim_geom(p):
    if isinstance(p, gp.Circle):
        return Point(p.x, p.y).buffer(p.r, 24)
    if isinstance(p, gp.Line):
        return LineString([(p.x1, p.y1), (p.x2, p.y2)]).buffer(p.width / 2, 12)
    if isinstance(p, gp.Arc):
        a0 = math.atan2(p.y1 - p.cy, p.x1 - p.cx); a1 = math.atan2(p.y2 - p.cy, p.x2 - p.cx)
        r = math.hypot(p.x1 - p.cx, p.y1 - p.cy)
        if p.clockwise:
            a0, a1 = a1, a0
        if a1 <= a0:
            a1 += 2 * math.pi
        pts = [(p.cx + r * math.cos(a0 + (a1 - a0) * i / 24), p.cy + r * math.sin(a0 + (a1 - a0) * i / 24)) for i in range(25)]
        return LineString(pts).buffer(p.width / 2, 12)
    if isinstance(p, gp.Rectangle):
        g = box(-p.w / 2, -p.h / 2, p.w / 2, p.h / 2)
        return translate(rotate(g, p.rotation, origin=(0, 0), use_radians=True), p.x, p.y)
    if isinstance(p, gp.ArcPoly):
        pts = list(p.outline)
        return Polygon(pts).buffer(0) if len(pts) >= 3 else Polygon()
    raise TypeError(type(p))

def cuivre(chemin):
    g = GerberFile.open(chemin)
    sombre, clairs = [], 0
    geom = Polygon()
    for o in g.objects:
        for p in o.to_primitives(unit=MM):
            pg = prim_geom(p)
            if p.polarity_dark:
                sombre.append(pg)
            else:
                clairs += 1
                geom = unary_union([geom] + sombre).difference(pg); sombre = []
    geom = unary_union([geom] + sombre)
    return geom, clairs

def trous(chemin):
    d = ExcellonFile.open(chemin)
    out = []
    for o in d.objects:
        dia = o.aperture.diameter
        if type(o).__name__ == 'Flash':
            out.append((Point(o.x, o.y).buffer(dia / 2, 16), dia))
        else:
            out.append((LineString([(o.x1, o.y1), (o.x2, o.y2)]).buffer(dia / 2, 16), dia))
    return out

F, clF = cuivre(fichier('F_Cu.gtl')); B, clB = cuivre(fichier('B_Cu.gbl'))
PTH = trous(fichier('-PTH.drl')); NPTH = trous(fichier('NPTH.drl'))
print(f"Cuivre lu : dessus {F.area:.0f} mm², dessous {B.area:.0f} mm² ; {len(PTH)} trous métallisés, {len(NPTH)} non métallisés")

# Pastilles attendues : position (fichiers des blocs, posés à leur place) et réseau (celui du bloc, nommé pour la carte)
def pad_geom(px, py, rot, q):
    w, h = q['width'], q['height']
    g = Point(0, 0).buffer(w / 2, 16) if q['shape'] == 'circle' else box(-w / 2, -h / 2, w / 2, h / 2)
    g = translate(rotate(g, q.get('rotation', 0), origin=(0, 0)), q['x'], q['y'])
    return translate(rotate(g, rot, origin=(0, 0)), px, py)
pads = []   # (étiquette, réseau, couches, point)
for b in CARTE.blocs:
    for p in b.design['parts']:
        px, py = b.point(p['x'], p['y'])
        ref = CARTE.repere(b, p['id'])
        for q in p['pads']:
            if q['type'] == 'npth':
                continue
            c = pad_geom(px, py, b.angle(p['rotation']), q).centroid
            net = CARTE.reseau(b, q.get('netName')) or f"(libre {ref}.{q['id']})"
            pads.append((f"{ref}.{q['id']}", net, ('F',) if q['type'] == 'smd' else ('F', 'B'), c))

# Morceaux de cuivre, reliés d'une face à l'autre par les trous métallisés
morceaux = []
for L, geom in (('F', F), ('B', B)):
    for g in (geom.geoms if hasattr(geom, 'geoms') else [geom]):
        morceaux.append((L, g))
parent = list(range(len(morceaux)))
def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]; i = parent[i]
    return i
arbre = STRtree([g for _, g in morceaux])
for h, _ in PTH:
    touches = [i for i in arbre.query(h) if morceaux[i][1].intersects(h)]
    for i in touches[1:]:
        parent[find(i)] = find(touches[0])
reseaux_du_morceau = defaultdict(set); morceau_du_pad = {}
for lab, net, lays, pt in pads:
    ids = {find(i) for i in arbre.query(pt) if morceaux[i][0] in lays and morceaux[i][1].covers(pt)}
    morceau_du_pad[lab] = ids
    for i in ids:
        reseaux_du_morceau[i].add(net)

print("== 1. Coupures (un réseau en plusieurs morceaux) ==")
par_reseau = defaultdict(list)
for lab, net, lays, pt in pads:
    par_reseau[net].append(lab)
coupes, sans_cuivre = 0, []
for net, labs in sorted(par_reseau.items()):
    if net.startswith('(libre'):
        continue
    groupes = defaultdict(list)
    for lab in labs:
        ids = morceau_du_pad[lab]
        if not ids:
            sans_cuivre.append(lab)
        groupes[min(ids) if ids else -1].append(lab)
    if len(groupes) > 1:
        coupes += 1
        print(f"  ✗ {net} : " + " | ".join(", ".join(v) for v in groupes.values()))
nets = [n for n in par_reseau if not n.startswith('(libre')]
print(f"  {len(nets) - coupes}/{len(nets)} réseaux d'un seul tenant" + (f" ; pastilles sans cuivre : {sans_cuivre}" if sans_cuivre else ""))
if coupes:
    A_CORRIGER.append(f"{coupes} réseau(x) coupé(s)")

print("== 2. Courts-circuits (un morceau de cuivre qui touche deux réseaux) ==")
cc = [(i, s) for i, s in reseaux_du_morceau.items() if len(s) > 1]
for i, s in cc:
    print(f"  ✗ {sorted(s)}")
print(f"  {len(cc)} court(s)-circuit(s)")
if cc:
    A_CORRIGER.append(f"{len(cc)} court(s)-circuit(s)")

print("== 3. Écart minimal entre cuivres de réseaux différents ==")
reseau_racine = {r: next(iter(s)) for r, s in reseaux_du_morceau.items() if len(s) == 1}
for L in ('F', 'B'):
    idx = [i for i, (l, _) in enumerate(morceaux) if l == L]
    geoms = [morceaux[i][1] for i in idx]
    t = STRtree(geoms); pire = (9, None)
    for a, ia in enumerate(idx):
        na = reseau_racine.get(find(ia), f'#{find(ia)}')
        for b in t.query(geoms[a].buffer(0.3)):
            ib = idx[b]
            if b <= a or find(ib) == find(ia):
                continue
            nb = reseau_racine.get(find(ib), f'#{find(ib)}')
            dist = geoms[a].distance(geoms[b])
            if dist < pire[0]:
                pire = (dist, (na, nb, geoms[a].centroid, geoms[b].centroid))
    if pire[1]:
        na, nb, ca, cb = pire[1]
        print(f"  face {'dessus' if L == 'F' else 'dessous'} : {pire[0]:.3f} mm ({na} ↔ {nb})")
        if pire[0] < REGLES['kicad']['min_clearance'] - 0.005:
            A_CORRIGER.append(f"écart de {pire[0]:.3f} mm entre {na} et {nb} (mini {REGLES['kicad']['min_clearance']} mm)")

print("== 4. Zones sans cuivre des blocs ==")
for raison, rect in CARTE.zones_sans_cuivre:
    z = box(*rect); sf, sb = F.intersection(z).area, B.intersection(z).area
    print(f"  {'✓' if sf + sb < 0.01 else '✗'} {raison} : cuivre dessus {sf:.2f} mm², dessous {sb:.2f} mm²")
    if sf + sb >= 0.01:
        A_CORRIGER.append(f"cuivre dans la zone interdite « {raison} »")
if not CARTE.zones_sans_cuivre:
    print("  aucune zone interdite dans ces blocs")

print("== 5. Cuivre au bord de la carte ==")
Rc = CARTE.rayon                 # le vrai contour, coins arrondis compris (près d'un coin, le cuivre est plus près du bord)
bord = (box(Rc, Rc, W - Rc, H - Rc).buffer(Rc, 64) if Rc > 0 else box(0, 0, W, H)).exterior
print(f"  distance minimale : dessus {F.distance(bord):.2f} mm, dessous {B.distance(bord):.2f} mm")
if min(F.distance(bord), B.distance(bord)) < REGLES['kicad']['min_copper_edge_clearance'] - 0.005:
    A_CORRIGER.append("cuivre trop près du bord")

print("== 6. Perçages ==")
dias = sorted({round(d, 2) for _, d in PTH}); dn = sorted({round(d, 2) for _, d in NPTH})
print(f"  métallisés : {dias} mm ; non métallisés : {dn} mm")

SEUIL_PTH, SEUIL_NPTH = REGLES['controle']['trou_metallise_cuivre'], REGLES['controle']['trou_non_metallise_cuivre']
print(f"== 7. Trous ↔ cuivre d'un autre réseau (mini {SEUIL_PTH} mm pour un trou métallisé, {SEUIL_NPTH} mm pour un trou non métallisé) ==")
def pire_trou(liste, metallise):
    pire = (9, None)
    for h, dia in liste:
        propres = {find(i) for i in arbre.query(h) if morceaux[i][1].intersects(h)} if metallise else set()
        for i in arbre.query(h.buffer(0.5)):
            if find(i) in propres:
                continue
            dist = morceaux[i][1].distance(h)
            if dist < pire[0]:
                pire = (dist, (h.centroid, dia, reseau_racine.get(find(i), '?'), morceaux[i][0]))
    return pire
for nom, liste, met in (('métallisés', PTH, True), ('non métallisés', NPTH, False)):
    d, info = pire_trou(liste, met)
    if info:
        c, dia, net, L = info
        print(f"  trous {nom} : {d:.3f} mm (trou Ø{dia} en ({c.x:.2f}, {c.y:.2f}) ↔ {net}, face {'dessus' if L == 'F' else 'dessous'})")
        if d < (SEUIL_PTH if met else SEUIL_NPTH) - 0.005:
            A_CORRIGER.append(f"trou {nom[:-1]} Ø{dia} en ({c.x:.2f}, {c.y:.2f}) à {d:.3f} mm du cuivre {net}")
# liste des trous métallisés trop près, pour savoir d'où ils viennent
proches = []
for h, dia in PTH:
    propres = {find(i) for i in arbre.query(h) if morceaux[i][1].intersects(h)}
    dmin = min([morceaux[i][1].distance(h) for i in arbre.query(h.buffer(0.5)) if find(i) not in propres] or [9])
    if dmin < SEUIL_PTH:
        proches.append((round(dmin, 3), round(h.centroid.x, 2), round(h.centroid.y, 2), dia))
print(f"  {len(proches)} trou(s) métallisé(s) à moins de {SEUIL_PTH} mm d'un autre réseau : {sorted(proches)[:12]}")

C_MIN, C_CONS = REGLES['controle']['couronne_min'], REGLES['controle']['couronne_conseillee']
print(f"== 8. Couronne des trous de composants ({C_MIN} mm mini, {C_CONS} conseillé) ==")
mini = []
for b in CARTE.blocs:
    for p in b.design['parts']:
        for q in p['pads']:
            if q['type'] in ('tht', 'pth', 'through') or (q['type'] not in ('smd', 'npth') and 'drill' in q):
                dr = q.get('drill', {}); dia = dr.get('diameter') or min(dr.get('width', 9), dr.get('height', 9))
                mini.append((round((min(q['width'], q['height']) - dia) / 2, 3), f"{CARTE.repere(b, p['id'])}.{q['id']}"))
mini.sort()
print(f"  plus petites : {mini[:5]}")
if mini and mini[0][0] < C_MIN - 0.005:
    A_CORRIGER.append(f"couronne de {mini[0][0]} mm sur {mini[0][1]}")

A = REGLES['alimentations']
print(f"== 9. Largeur du cuivre des alimentations (courant demandé, IPC-2221, +{A['echauffement_C']} °C) ==")
for net, i_a in sorted(CARTE.courants.items()):
    w = CARTE.largeur_mini(i_a)
    mes = [(lab, lays, pt) for lab, n, lays, pt in pads if n == net]
    racines = {find(i) for lab, _, _ in mes for i in morceau_du_pad[lab]}
    geo = []
    for i, (L, g) in enumerate(morceaux):
        if find(i) in racines:
            reduit = g.buffer(-w / 2 + 0.01, 8).buffer(w / 2 - 0.01, 8)     # ce qui reste là où le cuivre est assez large
            geo.append((L, reduit))
    # les pastilles du réseau restent des points d'entrée, même si elles sont plus étroites que la largeur demandée
    pas_geo = {}
    for lab, n, lays, pt in pads:
        if n == net:
            for i in morceau_du_pad[lab]:
                pass
    morceaux_l = []
    for L, g in geo:
        for p in (g.geoms if hasattr(g, 'geoms') else [g]):
            if not p.is_empty:
                morceaux_l.append((L, p))
    par = list(range(len(morceaux_l)))
    def fd(i):
        while par[i] != i:
            par[i] = par[par[i]]; i = par[i]
        return i
    for h, _ in PTH:
        t = [i for i, (L, p) in enumerate(morceaux_l) if p.intersects(h)]
        for i in t[1:]:
            par[fd(i)] = fd(t[0])
    groupes = defaultdict(list)
    for lab, lays, pt in mes:
        ids = {fd(i) for i, (L, p) in enumerate(morceaux_l) if L in lays and p.distance(pt) < 0.8}
        groupes[min(ids) if ids else -1].append(lab)
    etat = '✓' if len(groupes) == 1 else '✗'
    print(f"  {etat} {net} ({i_a} A → {w:.2f} mm mini) : " + (
        "partout assez large" if len(groupes) == 1 else "étranglements entre " + " | ".join(", ".join(v) for v in groupes.values())))
    if len(groupes) > 1:
        A_CORRIGER.append(f"alimentation {net} trop étroite par endroits")

print("== Bilan ==")
if A_CORRIGER:
    print(f"  {len(A_CORRIGER)} point(s) à corriger avant de commander :")
    for a in A_CORRIGER:
        print("  ✗", a)
else:
    print("  ✓ rien à corriger")
sys.exit(1 if A_CORRIGER else 0)
