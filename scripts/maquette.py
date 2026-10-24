"""Chaîne puzzle, étape 4 — « maquette à toucher » : la carte agrandie, à imprimer en 3D (CadQuery).
Pour montrer à quoi ressemble une carte (au FabLab, à un fabricant) et pour la vérifier du bout des doigts.
Sur la maquette :
  - la plaque a la forme de la carte, avec un coin coupé en haut à gauche pour savoir dans quel sens on la tient ;
  - les composants sont leurs vrais modèles 3D (bibliothèque easyeda2kicad), agrandis ;
  - les pistes du dessus sont en relief ; celles du dessous sont en creux, sous la plaque (retourner la maquette) ;
  - les sorties des blocs (pastilles de cuivre nu) sont des plots plus hauts que les pistes ;
  - une rainure sépare les blocs ; le nom de chaque bloc est écrit en braille dans le bloc, s'il y a la place,
    sinon dans la légende ; il est aussi écrit en grosses lettres en relief, pour les personnes qui voient ;
  - chaque bloc a sa texture en creux (lignes, quadrillage, trous…) et, dans les versions en couleurs, sa couleur :
    la couleur et la texture disent la même chose, l'une aux yeux, l'autre aux doigts ;
  - une bande de légende en braille (et en lettres), sous la carte : nom de la carte et échelle.
Réglages (échelle, hauteurs, braille, couleurs, textures, puzzle) : bibliotheque/regles/maquette.json.
Sorties, dans le dossier du projet :
  - maquette-a-toucher.stl : la maquette en un seul solide, d'une seule couleur (STEP aussi si « exporter_step ») ;
  - maquette-couleurs.3mf : la même, en une pièce, chaque partie avec sa couleur (imprimante à plusieurs bobines) ;
  - maquette-puzzle/*.stl : une pièce par bloc et le fond, à imprimer chacune dans sa couleur (imprimante à une bobine) ;
    chaque bloc se pose dans son logement du fond, sur une pente à 45° ; il peut s'enlever, ou se coller ;
  - maquette-impression.txt : ce qu'il faut dire à la personne qui imprime ;
  - maquette-plan.png : vue de dessus en couleurs, pour vérifier.
Usage : python3 maquette.py cartes/ma-carte.json dossier_projet/carte.kicad_pcb"""
import json, math, os, re, sys, time, unicodedata
import cadquery as cq
import pcbnew
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from description import Carte
from export_3mf import ecrire_3mf

CARTE = Carte(sys.argv[1])
PCB = sys.argv[2]
PROJET = os.path.dirname(os.path.abspath(PCB))
M = json.load(open(os.path.join(CARTE.bibliotheque, 'regles', 'maquette.json'), encoding='utf-8'))
E = M['echelle']; T = M['plaque_mm']; BR = M['braille']
W, H, R = CARTE.largeur * E, CARTE.hauteur * E, CARTE.rayon * E
BANDE = M['bande_legende_mm']
COUL = M.get('couleurs', {}); TX = M.get('textures', {}); PZ = M.get('puzzle', {}); TXT = M.get('texte', {})
debut = time.time()

# ---------- braille : par liblouis (module braille.py, table française) ; la maquette écrit en minuscules
import braille as BRL
def cellules(texte):
    return BRL.cellules(texte.lower())
def points_braille(texte, x0, y0):
    """Centres des points ; (x0, y0) = point 1 de la première cellule. Points 1-2-3 à gauche, 4-5-6 à droite."""
    return BRL.points(texte.lower(), x0, y0, BR)
def taille_braille(texte):
    return BRL.taille(texte.lower(), BR)

# ---------- outils géométriques
def mmxy(v):                       # KiCad (y vers le bas, nm) → maquette (y vers le haut, mm, agrandi)
    return pcbnew.ToMM(v.x) * E, -pcbnew.ToMM(v.y) * E

def polygones(g):
    if g.is_empty:
        return []
    if hasattr(g, 'geoms'):
        return [p for q in g.geoms for p in polygones(q)]
    return [g] if g.geom_type == 'Polygon' else []

def solide(poly, z0, h):
    """Polygone shapely (avec trous) → solide CadQuery entre z0 et z0 + h."""
    def fil(coords):
        pts = [cq.Vector(x, y, z0) for x, y in list(coords)[:-1]]
        return cq.Wire.makePolygon(pts, close=True)
    poly = poly.buffer(0)
    face = cq.Face.makeFromWires(fil(poly.exterior.coords), [fil(i.coords) for i in poly.interiors])
    return cq.Solid.extrudeLinear(face, cq.Vector(0, 0, h))

def coins_arrondis(w, h, r):
    return box(r, r, w - r, h - r).buffer(r, 16) if r > 0 else box(0, 0, w, h)

def ascii_nom(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

# ---------- lecture de la carte
board = pcbnew.LoadBoard(PCB)
non_poses = {CARTE.repere(b, r) for b in CARTE.blocs for r in b.bloc.get('non_poses', [])}

def piste(t):
    (x1, y1), (x2, y2) = mmxy(t.GetStart()), mmxy(t.GetEnd())
    return LineString([(x1, y1), (x2, y2)]).buffer(max(pcbnew.ToMM(t.GetWidth()) * E, 0.0) / 2, 8)

segments = [t for t in board.GetTracks() if t.GetClass() == 'PCB_TRACK']
L_dessus = M['pistes_dessus']['largeur_min_mm']; L_dessous = M['pistes_dessous']['largeur_min_mm']
dessus = unary_union([piste(t).buffer(max(0, (L_dessus - pcbnew.ToMM(t.GetWidth()) * E) / 2)) for t in segments if t.GetLayer() == pcbnew.F_Cu])
dessous = unary_union([piste(t).buffer(max(0, (L_dessous - pcbnew.ToMM(t.GetWidth()) * E) / 2)) for t in segments if t.GetLayer() == pcbnew.B_Cu])

sorties, trous, corps = [], [], []
for fp in board.GetFootprints():
    ref = fp.GetReference()
    for pad in fp.Pads():
        if pad.GetDrillSize().x and pcbnew.ToMM(pad.GetDrillSize().x) >= M['trou_reel_min_mm']:
            trous.append(Point(*mmxy(pad.GetPosition())).buffer(pcbnew.ToMM(pad.GetDrillSize().x) * E / 2, 16))
        if ref in non_poses and pad.IsOnLayer(pcbnew.F_Cu):
            bb = pad.GetBoundingBox()
            (xa, ya), (xb, yb) = mmxy(bb.GetOrigin()), mmxy(bb.GetEnd())
            sorties.append(box(min(xa, xb), min(ya, yb), max(xa, xb), max(ya, yb)))
    if ref not in non_poses and not fp.GetAttributes() & pcbnew.FP_BOARD_ONLY:   # trous de fixation : percés, pas de corps
        corps.append(fp)

# ---------- plaque : carte + bande de légende, coin repère, trous, rainures, pistes du dessous
contour = coins_arrondis(W, H, R)
bande = box(0, -BANDE, W, R + 1)
pleine = unary_union([contour, bande])
plaque2d = pleine
c = M['coin_repere_mm']
plaque2d = plaque2d.difference(Polygon([(-1, H + 1), (c, H + 1), (-1, H - c)]))
plaque2d = plaque2d.difference(unary_union(trous)) if trous else plaque2d

rainure = M['rainure_entre_blocs']
cadres = []
for b in CARTE.blocs:
    x0, y0 = b.position
    cadres.append(box(x0 * E, y0 * E, (x0 + b.taille[0]) * E, (y0 + b.taille[1]) * E))
rainures = unary_union([cd.exterior.buffer(rainure['largeur_mm'] / 2, 4) for cd in cadres]).intersection(contour.buffer(-1.5))
separation = LineString([(2, 0), (W - 2, 0)]).buffer(rainure['largeur_mm'] / 2, 4)   # entre carte et légende

plaque = cq.Workplane('XY')
morceaux_plaque = polygones(plaque2d)
plaque_solide = solide(morceaux_plaque[0], 0, T)
for p in morceaux_plaque[1:]:
    plaque_solide = plaque_solide.fuse(solide(p, 0, T))
a_creuser = []
for g in polygones(unary_union([rainures, separation])):
    a_creuser.append(solide(g, T - rainure['profondeur_mm'], rainure['profondeur_mm'] + 1))
for g in polygones(dessous.intersection(contour.buffer(-0.5))):
    a_creuser.append(solide(g, -1, 1 + M['pistes_dessous']['creux_mm']))
if a_creuser:
    plaque_solide = plaque_solide.cut(cq.Compound.makeCompound(a_creuser))

# ---------- reliefs : pistes du dessus, sorties
reliefs = []
pistes_visibles = dessus.difference(unary_union([rainures] + trous)).intersection(contour)
for g in polygones(pistes_visibles):
    if g.area > 0.05:
        reliefs.append(solide(g, T - 0.01, M['pistes_dessus']['relief_mm'] + 0.01))
for g in polygones(unary_union(sorties)):
    reliefs.append(solide(g, T - 0.01, M['sorties']['relief_mm'] + 0.01))

# ---------- composants : vrais modèles 3D, agrandis, coupés sous la plaque
modeles = {}
def modele(chemin_wrl):
    nom = os.path.splitext(os.path.basename(chemin_wrl))[0]
    if nom not in modeles:
        step = os.path.join(CARTE.empreintes, CARTE.nom_bib + '.3dshapes', nom + '.step')
        modeles[nom] = cq.importers.importStep(step).val() if os.path.exists(step) else None
    return modeles[nom]

sous_le_plateau = cq.Solid.makeBox(W + 40, H + BANDE + 40, 200, cq.Vector(-20, -BANDE - 20, 0))
emprises, sans_modele = [], []
for fp in corps:
    mdl = next(iter(fp.Models()), None)
    forme = modele(mdl.m_Filename) if mdl else None
    if forme is None:
        sans_modele.append(fp.GetReference()); continue
    f = forme.scale(E)
    f = f.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), mdl.m_Rotation.z)
    f = f.translate(cq.Vector(mdl.m_Offset.x * E, mdl.m_Offset.y * E, mdl.m_Offset.z * E))
    f = f.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), fp.GetOrientationDegrees())
    x, y = mmxy(fp.GetPosition())
    f = f.translate(cq.Vector(x, y, T)).intersect(sous_le_plateau)
    bb = f.BoundingBox()
    emprises.append(box(bb.xmin, bb.ymin, bb.xmax, bb.ymax))
    reliefs.append(f)

# ---------- braille et lettres : nom de chaque bloc dans le bloc (s'il y a la place), légende sous la carte
genants = unary_union(emprises + [pistes_visibles, unary_union(sorties), rainures] + trous).buffer(BR['marge_mm'])
def place_libre(cadre, lw, lh):
    """Emplacement libre de lw × lh, le plus proche du centre du bloc ; None s'il n'y en a pas."""
    cx, cy = cadre.centroid.x, cadre.centroid.y
    meilleur = None
    x0, y0, x1, y1 = cadre.bounds
    interieur = cadre.buffer(-2).intersection(contour)
    for i in range(int(x1 - x0 - lw) + 1):
        for j in range(int(y1 - y0 - lh) + 1):
            zone = box(x0 + i, y0 + j, x0 + i + lw, y0 + j + lh)
            if interieur.contains(zone) and not zone.intersects(genants):
                d = Point(zone.centroid).distance(Point(cx, cy))
                if meilleur is None or d < meilleur[0]:
                    meilleur = (d, zone)
    return meilleur[1] if meilleur else None

POLICE = TXT.get('police', '')
def texte_relief(txt, hauteur):
    """Lettres en relief, posées sur la plaque à l'origine ; renvoie (solide, largeur, hauteur, décalages)."""
    s = cq.Workplane('XY').text(txt, hauteur, TXT['relief_mm'] + 0.01, fontPath=POLICE, halign='left', valign='bottom').val()
    bb = s.BoundingBox()
    return s, bb.xlen, bb.ylen, bb.xmin, bb.ymin

# Le nom du bloc s'il tient dans le bloc ; sinon sa première lettre, expliquée dans la légende.
points, legende_blocs, places, ecrits = [], [], [], []
r = BR['point_diametre_mm'] / 2
lettres_prises = set()
for b, cadre in zip(CARTE.blocs, cadres):
    nom = b.bloc.get('etiquette', b.nom)
    # une lettre qui tient dans une seule cellule braille, et pas déjà prise par un autre bloc (la maquette écrit en minuscules)
    lettre = next((l for l in nom if l.isalpha() and len(cellules(l)) == 1 and l.lower() not in lettres_prises), nom[0])
    for texte in (nom, lettre):
        if texte == lettre:
            lettres_prises.add(lettre.lower())
        zone = place_libre(cadre, *taille_braille(texte))
        if zone:
            zx0, zy0, zx1, zy1 = zone.bounds
            points += points_braille(texte, zx0 + r, zy1 - r)
            genants = genants.union(zone.buffer(BR['marge_mm']))
            if texte == nom:
                places.append(f'{nom} (en entier dans le bloc)')
            else:
                legende_blocs.append(f'{texte} {nom}')
                places.append(f'{nom} (lettre « {texte} » dans le bloc, expliquée dans la légende)')
            break
    else:
        legende_blocs.append(f'{nom} sans repère')
        places.append(f'{nom} (aucune place dans le bloc)')

# Le même nom en grosses lettres en relief (pour les personnes qui voient), si la police est là et s'il y a la place.
lettres_absentes = []
if POLICE and os.path.exists(POLICE):
    for b, cadre in zip(CARTE.blocs, cadres):
        nom = b.bloc.get('etiquette', b.nom).upper()
        for hauteur in (TXT['hauteur_mm'], TXT['hauteur_mm'] * 0.75):
            s, lw, lh, dx, dy = texte_relief(nom, hauteur)
            zone = place_libre(cadre, lw, lh)
            if zone:
                zx0, zy0, _, _ = zone.bounds
                reliefs.append(s.translate(cq.Vector(zx0 - dx, zy0 - dy, T - 0.01)))
                genants = genants.union(zone.buffer(BR['marge_mm']))
                ecrits.append((nom, zone))
                break
        else:
            lettres_absentes.append(nom)
elif TXT:
    lettres_absentes.append(f'police introuvable ({POLICE}) : pas de lettres en relief')

MOTS = {2: 'deux', 2.5: 'deux et demi', 3: 'trois', 4: 'quatre', 5: 'cinq'}
lignes = [CARTE.donnees.get('etiquette', 'carte') + ' échelle ' + MOTS.get(E, '')]
if legende_blocs:
    lignes.append(' '.join(legende_blocs))
for k, ligne in enumerate(lignes):
    lw, _ = taille_braille(ligne)
    if lw > W - 8:
        raise ValueError(f"légende trop longue pour la largeur de la maquette : « {ligne} »")
    points += points_braille(ligne, 6 + r, -6 - r - k * BR['pas_ligne_mm'])
if len(lignes) * BR['pas_ligne_mm'] > BANDE - 4:
    raise ValueError('bande de légende trop étroite pour le nombre de lignes')
for x, y in points:
    reliefs.append(cq.Solid.makeSphere(BR['point_diametre_mm'] / 2, cq.Vector(x, y, T), angleDegrees1=0, angleDegrees2=90))
# La première ligne de la légende aussi en lettres, à droite du braille, si elle tient.
if POLICE and os.path.exists(POLICE):
    titre = f"{CARTE.donnees.get('etiquette', 'carte').upper()} — ÉCHELLE {E:g}"
    s, lw, lh, dx, dy = texte_relief(titre, TXT['hauteur_mm'] * 0.85)
    x_t = 6 + taille_braille(lignes[0])[0] + 10
    y_t = -6 - BR['ecart_points_mm'] - lh / 2
    if x_t + lw < W - 4:
        reliefs.append(s.translate(cq.Vector(x_t - dx, y_t - dy, T - 0.01)))
        ecrits.append((titre, box(x_t, y_t, x_t + lw, y_t + lh)))
    else:
        lettres_absentes.append(f'titre « {titre} » (pas la place dans la bande de légende)')

# ---------- textures en creux : une par bloc, dans les endroits libres du bloc
def motif(nom, zone):
    if nom == 'lisse' or zone.is_empty:
        return Polygon()
    x0, y0, x1, y1 = zone.bounds
    p, w = TX['pas_mm'], TX['largeur_mm']
    if nom in ('lignes', 'quadrillage'):
        n = int((x1 - x0 + y1 - y0) / p) + 2
        traits = [LineString([(x0 - (y1 - y0) + k * p, y0), (x0 + k * p, y1)]) for k in range(n)]
        if nom == 'quadrillage':
            traits += [LineString([(x0 + k * p, y0), (x0 + k * p - (y1 - y0), y1)]) for k in range(n)]
        g = unary_union(traits).buffer(w / 2, cap_style=2)
    elif nom == 'trous':
        pt = TX['pas_trous_mm']
        g = unary_union([Point(x0 + i * pt, y0 + j * pt).buffer(TX['diametre_trous_mm'] / 2, 8)
                         for i in range(int((x1 - x0) / pt) + 1) for j in range(int((y1 - y0) / pt) + 1)])
    else:
        raise ValueError(f'texture « {nom} » inconnue (maquette.json) : lignes, quadrillage, trous ou lisse')
    return g.intersection(zone)

textures_blocs, textures_2d = [], []
if TX:
    libres = genants.buffer(TX['marge_mm'])
    for k, cadre in enumerate(cadres):
        nom_t = TX['blocs'][k % len(TX['blocs'])]
        zone = cadre.buffer(-3).intersection(contour).difference(libres)
        g = motif(nom_t, zone)
        morceaux = [q for q in polygones(g) if q.area > 1.0]
        textures_blocs.append(nom_t)
        textures_2d += morceaux
    if textures_2d:
        plaque_solide = plaque_solide.cut(cq.Compound.makeCompound(
            [solide(q, T - TX['profondeur_mm'], TX['profondeur_mm'] + 1) for q in textures_2d]))

# ---------- un seul solide, exporté en STL (et en STEP si demandé)
tout = plaque_solide.fuse(*reliefs, glue=False).clean()
if not tout.isValid() or len(tout.Solids()) != 1:
    print(f"  attention : la fusion donne {len(tout.Solids())} solide(s), valide={tout.isValid()} ; export des morceaux séparés")
    tout = cq.Compound.makeCompound([plaque_solide] + reliefs)
stl = os.path.join(PROJET, 'maquette-a-toucher.stl')
cq.exporters.export(cq.Workplane('XY').add(tout), stl, tolerance=0.05, angularTolerance=0.3)
if M.get('exporter_step'):            # fichier exact, mais lourd (environ 90 Mo pour la carte radio)
    cq.exporters.export(cq.Workplane('XY').add(tout), os.path.join(PROJET, 'maquette-a-toucher.step'))
t_un = time.time() - debut

# ---------- versions en couleurs : en une pièce (3MF) et en puzzle (une pièce par bloc, plus le fond)
def rect_etendu(i):
    """Le cadre du bloc, prolongé jusqu'au-delà du bord de la carte sur les côtés qui touchent le bord
    (ou qui n'en sont séparés que par une bande trop mince pour faire une pièce solide)."""
    x0, y0, x1, y1 = cadres[i].bounds
    autres = unary_union([cd for j, cd in enumerate(cadres) if j != i]) if len(cadres) > 1 else Polygon()
    m, G = PZ['bande_absorbee_mm'], 60.0
    cotes = {'gauche': (box(x0 - m, y0, x0, y1), box(x0 - G, y0, x0 - m, y1)),
             'droite': (box(x1, y0, x1 + m, y1), box(x1 + m, y0, x1 + G, y1)),
             'bas': (box(x0, y0 - m, x1, y0), box(x0, y0 - G, x1, y0 - m)),
             'haut': (box(x0, y1, x1, y1 + m), box(x0, y1 + m, x1, y1 + G))}
    n = [x0, y0, x1, y1]
    for nom, (bord, au_dela) in cotes.items():
        touche_autre = bord.intersection(autres).area > 0.01 * bord.area
        rien_au_dela = au_dela.intersection(pleine).difference(autres).area < 1.0
        if rien_au_dela and not touche_autre:
            k = {'gauche': 0, 'bas': 1, 'droite': 2, 'haut': 3}[nom]
            n[k] += -G if k < 2 else G
    return box(*n)

def fil_rect(poly, z):
    x0, y0, x1, y1 = poly.bounds
    return cq.Wire.makePolygon([cq.Vector(x0, y0, z), cq.Vector(x1, y0, z), cq.Vector(x1, y1, z), cq.Vector(x0, y1, z)], close=True)

def region_assise(bas, haut, L):
    """Volume dont la section est « bas » sous z = 0, « haut » au-dessus de z = L, avec une pente entre les deux."""
    return cq.Solid.makeLoft([fil_rect(bas, -10), fil_rect(bas, 0), fil_rect(haut, L), fil_rect(haut, T + 500)], True)

def taille_xy(forme):
    """Taille au sol, prise sur le maillage (la boîte d'OpenCascade est un peu trop large)."""
    sommets, _ = forme.tessellate(0.1, 0.5)
    xs, ys = [v.x for v in sommets], [v.y for v in sommets]
    return max(xs) - min(xs), max(ys) - min(ys)

impression, puzzle, t_coul = [], [], 0
if COUL.get('actif'):
    t0 = time.time()
    rects = [rect_etendu(i) for i in range(len(cadres))]
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            if rects[i].intersection(rects[j]).area > 0.01:
                print(f'  attention : les pièces des blocs {CARTE.blocs[i].nom} et {CARTE.blocs[j].nom} se chevauchent')
    couleurs_blocs = [COUL['blocs'][k % len(COUL['blocs'])] for k in range(len(cadres))]
    fond_c, relief_c = COUL['fond'], COUL['reliefs']
    dessous_t = cq.Solid.makeBox(4000, 4000, T + 100, cq.Vector(-2000, -2000, -100))
    dessus_t = cq.Solid.makeBox(4000, 4000, 1000, cq.Vector(-2000, -2000, T))
    bas_tout = tout.intersect(dessous_t)       # la plaque, dans la couleur de chaque bloc
    haut_tout = tout.intersect(dessus_t)       # tout ce qui dépasse : pistes, plots, composants, braille, lettres

    # 1. En une pièce : la plaque coupée suivant les blocs (sans jeu), les reliefs en une seule couleur.
    parties, reste = [], bas_tout
    for b, rect, col in zip(CARTE.blocs, rects, couleurs_blocs):
        prisme = solide(rect, -50, T + 100)
        etiq = b.bloc.get('etiquette', b.nom)
        parties.append((f"{etiq} — plaque ({col['nom']})", col['rgb'], bas_tout.intersect(prisme)))
        reste = reste.cut(prisme)
    parties.append((f"fond et légende — plaque ({fond_c['nom']})", fond_c['rgb'], reste))
    parties.append((f"reliefs : pistes, composants, braille, lettres ({relief_c['nom']})", relief_c['rgb'], haut_tout))
    f3mf = os.path.join(PROJET, 'maquette-couleurs.3mf')
    n_parties, n_tri = ecrire_3mf(f3mf, parties, nom_piece=f"maquette {CARTE.donnees.get('etiquette', 'carte')}")

    # 2. En puzzle : chaque bloc est une pièce qui se pose dans le fond, sur une pente à 45°, avec un jeu.
    L, jeu = PZ['assise_mm'], PZ['jeu_mm']
    dossier = os.path.join(PROJET, 'maquette-puzzle')
    os.makedirs(dossier, exist_ok=True)
    for f in os.listdir(dossier):
        if f.endswith('.stl'):
            os.remove(os.path.join(dossier, f))
    def prismes(g, z0, h):
        return cq.Compound.makeCompound([solide(p, z0, h) for p in polygones(g)])
    # Au-dessus de la plaque, un bloc emporte aussi ses composants entiers, même s'ils débordent de son cadre
    # (la prise USB-C qui dépasse du bord de la carte, par exemple).
    dessus_bloc = [unary_union([rect] + [e for e in emprises if cadre.contains(e.centroid)]) for rect, cadre in zip(rects, cadres)]
    logements = []
    for k, (b, rect, col) in enumerate(zip(CARTE.blocs, rects, couleurs_blocs), start=1):
        region = region_assise(rect.buffer(-(L + jeu), join_style=2), rect.buffer(-jeu, join_style=2), L)
        logements.append(region_assise(rect.buffer(-L, join_style=2), rect, L))
        morceau_bas = bas_tout.intersect(region)
        morceau_haut = haut_tout.intersect(prismes(dessus_bloc[k - 1].buffer(-jeu, join_style=2), T - 1, 600))
        etiq = b.bloc.get('etiquette', b.nom)
        puzzle.append((f'{k:02d}-{ascii_nom(etiq)}-{ascii_nom(col["nom"])}.stl', etiq, col['nom'],
                       textures_blocs[k - 1] if textures_blocs else 'lisse', morceau_bas, morceau_haut))
    reg_fond = cq.Solid.makeBox(4000, 4000, T + 20, cq.Vector(-2000, -2000, -10)).cut(cq.Compound.makeCompound(logements))
    fond_bas = bas_tout.intersect(reg_fond)
    fond_haut = haut_tout.cut(prismes(unary_union(dessus_bloc), T - 1, 600))
    morceaux_fond = fond_bas.Solids()
    hauts = fond_haut.Solids()
    for m_i, mb in enumerate(sorted(morceaux_fond, key=lambda s: -s.Volume())):
        if mb.Volume() < 1:
            continue
        bbm = mb.BoundingBox()
        dedans = [h for h in hauts if bbm.xmin <= h.Center().x <= bbm.xmax and bbm.ymin <= h.Center().y <= bbm.ymax]
        suffixe = '' if len(morceaux_fond) == 1 else f'-{m_i + 1}'
        k = len(puzzle) + 1
        puzzle.append((f'{k:02d}-fond{suffixe}-{ascii_nom(fond_c["nom"])}.stl', 'fond et légende' + suffixe, fond_c['nom'],
                       TX.get('fond', 'lisse'), mb, cq.Compound.makeCompound(dedans) if dedans else None))
    plateau = M.get('plateau_mm', [0, 0])
    for nom_f, etiq, col_nom, tex, mb, mh in puzzle:
        piece = cq.Compound.makeCompound([s for s in (mb, mh) if s is not None])
        cq.exporters.export(cq.Workplane('XY').add(piece), os.path.join(dossier, nom_f), tolerance=0.05, angularTolerance=0.3)
        lx, ly = taille_xy(piece)
        tient = plateau[0] and min(lx, ly) <= min(plateau) and max(lx, ly) <= max(plateau)
        impression.append((nom_f, etiq, col_nom, tex, lx, ly, tient))
    t_coul = time.time() - t0

    # Ce qu'il faut dire à la personne qui imprime.
    with open(os.path.join(PROJET, 'maquette-impression.txt'), 'w', encoding='utf-8') as f:
        f.write(f"Maquette à toucher — {CARTE.nom} — échelle {E:g}, plaque de {T:g} mm\n\n")
        f.write("Deux façons de l'imprimer :\n\n")
        f.write("1. Imprimante à plusieurs bobines : maquette-couleurs.3mf, en une seule pièce.\n"
                "   Chaque partie porte le nom de sa couleur :\n")
        for nom_p, rgb, _ in parties:
            f.write(f"   - {nom_p} ({rgb})\n")
        f.write(f"\n2. Imprimante à une bobine : les pièces du dossier maquette-puzzle, chacune dans sa couleur.\n"
                f"   Facultatif : à {T:g} mm de hauteur, faire une pause et passer au fil {relief_c['nom']} ; "
                f"les pistes, les composants, le braille et les lettres ressortent alors en {relief_c['nom']}.\n")
        for nom_f, etiq, col_nom, tex, lx, ly, tient in impression:
            dim = f"{lx:.0f} × {ly:.0f} mm"
            note = '' if not plateau[0] else ('' if tient else f" — plus grand qu'un plateau de {plateau[0]} × {plateau[1]} mm")
            f.write(f"   - {nom_f} : {etiq}, fil {col_nom}, texture « {tex} », {dim}{note}\n")
        f.write(f"\n   Assemblage : chaque bloc se pose dans son logement du fond, sur une pente à 45° (jeu de {str(jeu).replace('.', ',')} mm).\n"
                "   Il peut s'enlever, comme un bloc qu'on change dans la chaîne puzzle, ou se coller pour de bon.\n"
                "   Posée sur une table, la maquette tient seule ; pour la tenir en main ou toucher le dessous (pistes en creux),\n"
                "   retirer les blocs ou les coller.\n\n")
        f.write("Textures (en creux, une par bloc) : " +
                ', '.join(f"{b.bloc.get('etiquette', b.nom)} = {t}" for b, t in zip(CARTE.blocs, textures_blocs)) +
                f", fond = {TX.get('fond', 'lisse')}.\n")
        f.write("La couleur et la texture disent la même chose : l'une aux yeux, l'autre aux doigts.\n\n")
        f.write("Supports : les prises et l'antenne débordent ou sont en porte-à-faux ; prévoir des supports à ces endroits.\n")

# ---------- vue de dessus pour vérifier, en couleurs
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(W / 18, (H + BANDE) / 18))
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MPath
def dessine(g, **k):
    for p in polygones(g):
        anneaux = [p.exterior] + list(p.interiors)
        sommets = [pt for a in anneaux for pt in a.coords]
        codes = [c for a in anneaux for c in [MPath.MOVETO] + [MPath.LINETO] * (len(a.coords) - 2) + [MPath.CLOSEPOLY]]
        ax.add_patch(PathPatch(MPath(sommets, codes), linewidth=0, **k))
if COUL.get('actif'):
    dessine(plaque2d, color=COUL['fond']['rgb'])
    for rect, col in zip(rects, couleurs_blocs):
        dessine(plaque2d.intersection(rect), color=col['rgb'])
else:
    dessine(plaque2d, color='#e8e2d0')
dessine(unary_union(textures_2d) if textures_2d else Polygon(), color='#000000', alpha=0.25)
dessine(rainures, color='#555555', alpha=0.6); dessine(separation, color='#555555', alpha=0.6)
dessine(dessous.intersection(contour), color='#ffffff', alpha=0.35); dessine(pistes_visibles, color='#222222')
dessine(unary_union(sorties), color='#000000'); dessine(unary_union(emprises), color='#333333', alpha=0.7)
ax.set_xlim(-2, W + 2); ax.set_ylim(-BANDE - 2, H + 2)
ax.set_aspect('equal'); ax.axis('off')
fig.canvas.draw()
pt_par_mm = ax.get_window_extent().width / (W + 4) / fig.dpi * 72      # taille du texte du plan à l'échelle
for txt, zone in ecrits:
    ax.text(zone.centroid.x, zone.centroid.y, txt, ha='center', va='center', fontsize=(zone.bounds[3] - zone.bounds[1]) / 0.73 * pt_par_mm,
            color='#111111', weight='bold')
ax.scatter([p[0] for p in points], [p[1] for p in points], s=6, color='#111111')
ax.set_aspect('equal'); ax.axis('off')
fig.savefig(os.path.join(PROJET, 'maquette-plan.png'), dpi=110, bbox_inches='tight')

taille = os.path.getsize(stl) / 1e6
print(f"Maquette : {stl} ({taille:.1f} Mo) — {W:.0f} × {H + BANDE:.0f} mm, échelle {E}, plaque {T} mm ({t_un:.0f} s)")
print(f"  {len(corps) - len(sans_modele)} composants en 3D, {len(polygones(unary_union(sorties)))} sorties en plots, "
      f"{len(points)} points de braille ; légende : {' / '.join(lignes)}")
print('  noms des blocs :', ', '.join(places))
print('  en lettres :', ', '.join(t for t, _ in ecrits) or 'aucune', ('; manquent : ' + ', '.join(lettres_absentes)) if lettres_absentes else '')
if textures_blocs:
    print('  textures :', ', '.join(f"{b.bloc.get('etiquette', b.nom)} = {t}" for b, t in zip(CARTE.blocs, textures_blocs)))
if COUL.get('actif'):
    print(f"  en couleurs : maquette-couleurs.3mf ({n_parties} parties, {os.path.getsize(f3mf) / 1e6:.1f} Mo) ; "
          f"puzzle : {len(impression)} pièces dans maquette-puzzle/ ({t_coul:.0f} s)")
    for nom_f, etiq, col_nom, tex, lx, ly, tient in impression:
        print(f"    {nom_f} : {lx:.0f} × {ly:.0f} mm" + ('' if tient or not M.get('plateau_mm') else ' — plus grand que le plateau prévu'))
if sans_modele:
    print('  sans modèle 3D (non représentés) :', ', '.join(sans_modele))
