"""Chaîne puzzle, étape 0 ter — plan à toucher sur papier gonflé (papier thermogonflé : PIAF, Zychem…).
Sans KiCad : seulement la description de la carte, comme l'étape 0. On sent donc une disposition des blocs en quelques
minutes, avant de router et sans attendre une impression 3D. La maquette 3D (étape 4) reste le modèle détaillé.
Un PDF A4 à l'italienne, à imprimer à 100 % sur papier gonflé :
  page 1, la carte : contour (trait épais), blocs (tirets) avec leur nom en braille, sorties (petits carrés pleins),
          prises et fils (pavés pleins), trous de fixation (anneaux), zones sans cuivre (hachures) ;
  page 2, les liaisons : un trait droit d'une sortie à sa partenaire, dans un autre bloc ;
  sur ces deux pages, à gauche : le titre en braille, puis la clé des symboles (un mot en braille par symbole) ;
  page 3 et suivantes, la légende en braille : les sorties dans l'ordre de lecture, les prises, les trous, les zones.
Règles chiffrées : bibliotheque/regles/plan_tactile.json (avec leurs sources). Tout ce qui est noir gonfle ; le texte
pour les personnes qui voient est en bleu, il ne gonfle pas.
Sorties : plan-tactile.pdf ; plan-tactile-page-N.svg (à retoucher dans Inkscape) et .png (pour vérifier) ;
plan-tactile.txt (notice, la légende en texte pour le lecteur d'écran, les contrôles).
Usage : python3 plan_tactile.py cartes/ma-carte.json dossier/    (code de sortie 1 si un contrôle échoue)"""
import json, math, os, re, sys, textwrap, time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import PathPatch
from matplotlib.path import Path
from shapely.geometry import LineString, Point, box
from shapely.geometry.polygon import orient
from shapely.ops import substring, unary_union
from description import Carte, ROTATIONS
import braille as BRL

CARTE = Carte(sys.argv[1])
DOSSIER = sys.argv[2]
os.makedirs(DOSSIER, exist_ok=True)
R = json.load(open(os.path.join(CARTE.bibliotheque, 'regles', 'plan_tactile.json'), encoding='utf-8'))
BR, TABLE = R['braille'], R.get('table_braille', BRL.TABLE)
W, H = R['papier']['largeur_mm'], R['papier']['hauteur_mm']
M, T = R['marge_mm'], R['traits_mm']
VIDE, VIDE_MIN = R['vide_autour_mm'], R['vide_min_mm']
BLEU, HT = R['texte_voyant']['couleur'], R['texte_voyant']['hauteur_mm']
PAS = BR['pas_ligne_mm']
NOM = CARTE.donnees.get('etiquette', CARTE.nom).lower()
NOMS_COURTS = CARTE.donnees.get('noms_courts', {})
COTES = {'gauche': (-1, 0), 'droite': (1, 0), 'bas': (0, -1), 'haut': (0, 1)}
NOM_COTE = {v: k for k, v in COTES.items()}
BORD = {'gauche': 'bord gauche', 'droite': 'bord droit', 'bas': 'bord bas', 'haut': 'bord haut'}
# chaque symbole : le mot écrit en braille dans la clé, et ce que dit la notice
SYMBOLES = {'contour': ('carte', 'trait épais', 'le bord de la carte'),
            'bloc': ('bloc', 'tirets', "le bord d'un bloc ; son nom est écrit en braille dedans"),
            'sortie': ('sortie', 'petit carré plein', "une sortie d'un bloc (pastille de test)"),
            'prise': ('prise', 'pavé plein', 'une prise ou un fil'),
            'trou': ('trou', 'anneau', 'un trou de fixation'),
            'zone': ('zone', 'hachures', 'une zone sans cuivre (antenne)'),
            'liaison': ('liaison', 'trait fin', 'une liaison entre deux sorties de même nom')}
controles = []


def ctrl(etat, texte):
    """etat : True (✓), False (✗) ou None (⚠, à regarder)."""
    controles.append(('✓' if etat else '⚠' if etat is None else '✗') + ' ' + texte)


def nom_court(reseau):
    """Même règle que le banc de test : le nom donné par la carte (« noms_courts »), sinon la fin du nom."""
    return NOMS_COURTS.get(reseau, reseau.split('_')[-1][:6])


def num(v):
    return f"{v:g}".replace('.', ',')


# ---------- outils de dessin : tout ce qui est noir est un polygone exact, celui qui gonflera
def trait(ligne, largeur, plat=False):
    return ligne.buffer(largeur / 2, cap_style='flat' if plat else 'round', join_style='round')


def tirets(lignes, largeur):
    """Lignes (LineString ou MultiLineString) → tirets pleins, longueurs exactes en mm."""
    plein, vide = R['tirets_bloc_mm']
    morceaux = []
    for l in getattr(lignes, 'geoms', [lignes]):
        if l.is_empty or l.geom_type != 'LineString':
            continue
        d = 0.0
        while d < l.length:
            fin = min(d + plein, l.length)
            if fin - d >= 2.0:                         # pas de miettes : un bout de moins de 2 mm se confond avec un point
                morceaux.append(trait(substring(l, d, fin), largeur, plat=True))
            d += plein + vide
    return unary_union(morceaux)


def hachures(zone, pas_mm, largeur):
    """Hachures à 45° dans une zone."""
    if zone.is_empty:
        return zone
    x0, y0, x1, y1 = zone.bounds
    pas, ls = pas_mm * math.sqrt(2), []
    k = y0 - (x1 - x0) - pas
    while k < y1 + pas:
        l = LineString([(x0 - 1, k), (x1 + 1, k + (x1 - x0) + 2)]).intersection(zone)
        if not l.is_empty:
            ls.append(trait(l, largeur, plat=True))
        k += pas
    return unary_union(ls)


def cellules(texte):
    return len(BRL.cellules(texte.lower(), TABLE))


def taille_braille(texte):
    return BRL.taille(texte.lower(), BR, TABLE)


def texte_braille(texte, x_gauche, y_haut):
    """Points braille (disques) d'un texte ; (x_gauche, y_haut) = coin haut gauche du cadre du texte."""
    d = BR['point_diametre_mm']
    pts = BRL.points(texte.lower(), x_gauche + d / 2, y_haut - d / 2, BR, TABLE)
    return unary_union([Point(x, y).buffer(d / 2, 16) for x, y in pts])


def cellules_max(largeur):
    return int((largeur - BR['point_diametre_mm'] - BR['ecart_points_mm']) // BR['pas_cellule_mm']) + 1


def couper(texte, nmax):
    """Coupe un texte en lignes de braille d'au plus nmax cellules (mesurées après traduction par liblouis)."""
    lignes, courante = [], ''
    for mot in texte.split():
        essai = (courante + ' ' + mot).strip()
        if cellules(essai) <= nmax or not courante:
            courante = essai
        else:
            lignes.append(courante)
            courante = mot
    if courante:
        lignes.append(courante)
    return lignes


def bloc_braille(texte, x, y_haut, largeur):
    """Un texte braille coupé en lignes ; rend (géométrie, y sous la dernière ligne)."""
    ls = couper(texte, cellules_max(largeur))
    g = unary_union([texte_braille(l, x, y_haut - i * PAS) for i, l in enumerate(ls)])
    return g, y_haut - len(ls) * PAS


def position_dans(x, y, x0, y0, x1, y1):
    """« en haut à gauche », « au milieu »… d'un point dans un rectangle, par tiers."""
    fx, fy = (x - x0) / max(x1 - x0, 1e-9), (y - y0) / max(y1 - y0, 1e-9)
    h = 'à gauche' if fx < 1 / 3 else 'à droite' if fx > 2 / 3 else ''
    v = 'en bas' if fy < 1 / 3 else 'en haut' if fy > 2 / 3 else ''
    return ' '.join(m for m in (v, h) if m) or 'au milieu'


def cote_sur_carte(b, cote_local):
    nx, ny = ROTATIONS[b.rotation](*COTES[cote_local])
    return NOM_COTE[(round(nx), round(ny))]


# ---------- 1. échelle : la carte prend toute la page, sauf la colonne de gauche (titre, clé, texte bleu)
COLG = R['colonne_titre_mm']
LIBRE_L, LIBRE_H = W - 2 * M - COLG - VIDE, H - 2 * M
S = math.floor(min(LIBRE_L / CARTE.largeur, LIBRE_H / CARTE.hauteur) * 20) / 20   # au 0,05 près, plus simple à dire
OX = M + COLG + VIDE + (LIBRE_L - S * CARTE.largeur) / 2
OY = M + (LIBRE_H - S * CARTE.hauteur) / 2
ctrl(S >= R['echelle_min'], f"la carte tient sur la page ({R['papier']['nom']}), agrandie {num(S)} fois : "
     f"{S * CARTE.largeur:.0f} × {S * CARTE.hauteur:.0f} mm")


def P(x, y):
    return OX + S * x, OY + S * y


def rect_page(x0, y0, x1, y1):
    (a, b), (c, d) = P(x0, y0), P(x1, y1)
    return box(min(a, c), min(b, d), max(a, c), max(b, d))


# ---------- 2. ce qu'il y a sur la carte (en coordonnées de la page)
r = CARTE.rayon * S
cadre_carte = box(*P(0, 0), *P(CARTE.largeur, CARTE.hauteur))
if r > 0:
    cadre_carte = cadre_carte.buffer(-r, join_style='mitre').buffer(r, 32)
contour = trait(cadre_carte.exterior, T['contour'])
bande_contour = cadre_carte.exterior.buffer(VIDE_MIN + T['contour'] / 2)

# sorties
c2 = R['sortie_carre_mm'] / 2
sorties = []
for b in CARTE.blocs:
    w, h = b.design['board']['width'], b.design['board']['height']
    for p in b.design['parts']:
        if p['id'] not in b.bloc.get('non_poses', []):
            continue
        reseaux = sorted({CARTE.reseau(b, q.get('netName')) for q in p['pads']} - {None})
        dist = {'gauche': p['x'], 'droite': w - p['x'], 'bas': p['y'], 'haut': h - p['y']}
        x, y = P(*b.point(p['x'], p['y']))
        ref = CARTE.repere(b, p['id'])
        m = re.fullmatch(r'TP(\d+)', ref)
        sorties.append(dict(bloc=b, ref=ref, numero=m.group(1) if m else ref, reseau=reseaux[0] if reseaux else '?',
                            xy=(x, y), cote=cote_sur_carte(b, min(dist, key=dist.get)),
                            geom=box(x - c2, y - c2, x + c2, y + c2)))

# prises et fils (« boitier » des blocs) : le rectangle de leurs pastilles, au moins prise_min_mm de côté
prises = []
for b in CARTE.blocs:
    bt = b.bloc.get('boitier', {})
    for genre, cle in (('prise', 'ouvertures'), ('fil', 'fils')):
        for e in bt.get(cle, []):
            p = next((p for p in b.design['parts'] if p['id'] == e['ref']), None)
            if p is None:
                ctrl(False, f"{e['ref']} ({e.get('texte', '')}) : composant introuvable dans le bloc {b.id}")
                continue
            xs, ys = [], []
            for q in p['pads']:
                cx, cy = b.pastille(p, q)
                demi = max(q.get('width', 0), q.get('height', 0)) / 2
                xs += [cx - demi, cx + demi]
                ys += [cy - demi, cy + demi]
            g = rect_page(min(xs), min(ys), max(xs), max(ys))
            gx0, gy0, gx1, gy1 = g.bounds
            mini, cx, cy = R['prise_min_mm'], (gx0 + gx1) / 2, (gy0 + gy1) / 2
            dx, dy = max(mini, gx1 - gx0) / 2, max(mini, gy1 - gy0) / 2
            prises.append(dict(bloc=b, ref=e['ref'], genre=genre, texte=e.get('texte', e['ref']).lower(),
                               geom=box(cx - dx, cy - dy, cx + dx, cy + dy), carte=(min(xs), min(ys), max(xs), max(ys))))

# trous de fixation : anneaux, au diamètre du perçage
trous = []
if CARTE.trou:
    rr = CARTE.trou['diametre_trou_mm'] / 2 * S
    for i, (x, y) in enumerate(CARTE.trous_fixation, 1):
        trous.append(dict(n=i, xy=(x, y), geom=trait(Point(*P(x, y)).buffer(rr, 32).exterior, T['trou'])))

# zones sans cuivre : hachures, tenues à l'écart du contour
zones = []
for nom, (x0, y0, x1, y1) in CARTE.zones_sans_cuivre:
    zone = rect_page(x0, y0, x1, y1).difference(bande_contour).buffer(-T['hachures'] / 2)
    g = hachures(zone, R['hachures_pas_mm'], T['hachures'])
    if g.is_empty:
        continue
    bloc_id, raison = nom.split(' : ', 1)
    zones.append(dict(bloc=next(b for b in CARTE.blocs if b.id == bloc_id), geom=g, carte=(x0, y0, x1, y1),
                      raison=re.sub(r'\s*\(.*?\)', '', raison).strip().lower()))

# blocs : tirets ; le bord s'interrompt là où il longe le contour (le contour y est déjà) et là où un objet le touche presque
proches = unary_union([s['geom'] for s in sorties] + [p['geom'] for p in prises] + [t['geom'] for t in trous] + [z['geom'] for z in zones])
interdit = unary_union([proches.buffer(VIDE_MIN + T['bloc'] / 2), cadre_carte.exterior.buffer(VIDE_MIN + (T['contour'] + T['bloc']) / 2)])
blocs = []
for b in CARTE.blocs:
    cadre = rect_page(b.position[0], b.position[1], b.position[0] + b.taille[0], b.position[1] + b.taille[1])
    blocs.append(dict(bloc=b, cadre=cadre, geom=tirets(cadre.exterior.difference(interdit), T['bloc']),
                      etiquette=b.bloc.get('etiquette', b.id).lower()))

# liaisons : pour chaque réseau, l'arbre le plus court entre sorties de blocs différents (comme le chevelu de KiCad)
liaisons = []
par_reseau = {}
for s in sorties:
    par_reseau.setdefault(s['reseau'], []).append(s)
for reseau, ss in sorted(par_reseau.items()):
    if len({id(s['bloc']) for s in ss}) < 2:
        continue
    dans, reste = [ss[0]], ss[1:]
    while reste:
        a, bb = min(((a, bb) for a in dans for bb in reste if a['bloc'] is not bb['bloc']),
                    key=lambda ab: math.dist(ab[0]['xy'], ab[1]['xy']), default=(None, None))
        if a is None:
            break
        ligne = LineString([a['xy'], bb['xy']])
        liaisons.append(dict(reseau=reseau, a=a, b=bb, ligne=ligne, geom=trait(ligne, T['liaison']),
                             nom=f"liaison {nom_court(reseau)} ({a['numero']}-{bb['numero']})"))
        dans.append(bb)
        reste.remove(bb)


# ---------- 3. colonne de gauche des pages 1 et 2 : titre braille, clé des symboles, texte bleu
def colonne(titre, genres, bleus):
    """Rend (géométrie noire, cadre noir, lignes bleues)."""
    noir, y = bloc_braille(titre, M, H - M, COLG)
    morceaux = [noir]
    y -= PAS / 2
    larg_ech = 14.0
    for g in genres:
        mot = SYMBOLES[g][0]
        centre = y - taille_braille(mot)[1] / 2
        morceaux.append(echantillon(g, M + larg_ech / 2, centre))
        morceaux.append(texte_braille(mot, M + larg_ech + 4, y))
        y -= 13.0
    noir = unary_union(morceaux)
    lignes, yb = [], noir.bounds[1] - 6
    for l in bleus:
        for morceau in textwrap.wrap(l, 24):
            lignes.append((M, yb, morceau))
            yb -= HT * 1.6
        yb -= HT * 0.6
    if yb < M:
        ctrl(None, f"colonne de gauche ({titre}) : le texte bleu dépasse en bas de la page")
    if noir.bounds[2] > M + COLG + 0.01:
        ctrl(False, f"colonne de gauche ({titre}) : la clé déborde sur la carte")
    return noir, box(*noir.bounds), lignes


def echantillon(genre, cx, cy):
    """Le symbole tel qu'il est sur le plan, centré en (cx, cy), dans 14 mm de large."""
    if genre == 'contour':
        return trait(LineString([(cx - 6, cy), (cx + 6, cy)]), T['contour'])
    if genre == 'bloc':
        return tirets(LineString([(cx - 7, cy), (cx + 7, cy)]), T['bloc'])
    if genre == 'sortie':
        return box(cx - c2, cy - c2, cx + c2, cy + c2)
    if genre == 'prise':
        return box(cx - 5, cy - 3, cx + 5, cy + 3)
    if genre == 'trou':
        return trait(Point(cx, cy).buffer(min(CARTE.trou['diametre_trou_mm'] / 2 * S, 4.5), 32).exterior, T['trou'])
    if genre == 'zone':
        return hachures(box(cx - 5, cy - 5, cx + 5, cy + 5), R['hachures_pas_mm'], T['hachures'])
    if genre == 'liaison':
        return trait(LineString([(cx - 6, cy), (cx + 6, cy)]), T['liaison'])


genres1 = ['contour', 'bloc', 'sortie'] + (['prise'] if prises else []) + (['trou'] if trous else []) + (['zone'] if zones else [])
genres2 = ['contour', 'bloc', 'sortie'] + (['liaison'] if liaisons else [])
commun = [CARTE.nom, f"agrandie {num(S)} fois", "à imprimer à 100 % sur papier gonflé", "le bleu ne gonfle pas"]
col1, cadre_c1, bleus1 = colonne(f"{NOM} : carte", genres1, [commun[0], "page 1 : la carte"] + commun[1:])
col2, cadre_c2, bleus2 = colonne(f"{NOM} : liaisons", genres2, [commun[0], "page 2 : les liaisons entre blocs"] + commun[1:])

# ---------- 4. noms des blocs en braille
objets_p1 = [('contour', 'bord de la carte', contour), ('titre', 'colonne de gauche', cadre_c1)]
objets_p2 = [('contour', 'bord de la carte', contour), ('titre', 'colonne de gauche', cadre_c2)]
for o in (objets_p1, objets_p2):
    o += [('sortie', f"sortie {s['numero']}", s['geom']) for s in sorties]
    o += [('bloc', f"bord du bloc {bl['etiquette']}", bl['geom']) for bl in blocs]
objets_p1 += [('prise', f"{p['genre']} {p['texte']}", p['geom']) for p in prises]
objets_p1 += [('trou', f"trou de fixation {t['n']}", t['geom']) for t in trous]
objets_p1 += [('zone', f"zone sans cuivre ({z['raison']})", z['geom']) for z in zones]
objets_p2 += [('liaison', l['nom'], l['geom']) for l in liaisons]


def placer(texte, cadre, obstacles):
    """Le nom d'un bloc, dans le bloc, le plus près du coin haut gauche (début de lecture), à VIDE de tout le reste ;
    sinon à VIDE_MIN. Rend (géométrie, écart obtenu) ou None."""
    bw, bh = taille_braille(texte)
    obst = unary_union(obstacles)
    x0, y0, x1, y1 = cadre.bounds
    for vide in (VIDE, VIDE_MIN):
        yt = y1 - vide - T['bloc'] / 2
        while yt - bh >= y0 + vide:
            xl = x0 + vide + T['bloc'] / 2
            while xl + bw <= x1 - vide:
                if box(xl, yt - bh, xl + bw, yt).distance(obst) >= vide:
                    return texte_braille(texte, xl, yt), vide
                xl += 1.0
            yt -= 1.0
    return None


def noms_des_blocs(objets, nom_page):
    out = []
    for bl in blocs:
        res = placer(bl['etiquette'], bl['cadre'], [g for _, _, g in objets] + [g for _, g in out])
        if res is None:
            ctrl(False, f"{nom_page} : pas de place pour écrire « {bl['etiquette']} » en braille dans son bloc")
            continue
        g, vide = res
        if vide < VIDE:
            ctrl(None, f"{nom_page} : le nom « {bl['etiquette']} » n'a que {num(vide)} mm de vide autour (il en faudrait {num(VIDE)})")
        out.append((f"nom {bl['etiquette']}", g))
    objets += [('nom', n, g) for n, g in out]
    return [g for _, g in out]


noms1 = noms_des_blocs(objets_p1, 'page 1')
noms2 = noms_des_blocs(objets_p2, 'page 2')


# ---------- 5. contrôles d'écart (sur ce qui sera vraiment imprimé)
def ecarts(objets, nom_page):
    bouts = {l['nom']: {f"sortie {l['a']['numero']}", f"sortie {l['b']['numero']}"} for l in liaisons}
    trop_pres = []
    for i, (g1, n1, a) in enumerate(objets):
        for g2, n2, b in objets[i + 1:]:
            paire = {g1, g2}
            if paire == {'prise', 'contour'}:          # une prise au bord touche le bord : c'est voulu
                continue
            if 'liaison' in paire:
                if paire & {'bloc', 'contour'} or paire == {'liaison'}:
                    continue                            # un trait traverse un bord de bloc ; les croisements sont comptés à part
                l, autre = (n1, n2) if g1 == 'liaison' else (n2, n1)
                if autre in bouts[l]:
                    continue                            # ses deux bouts
            d = a.distance(b)
            if d < VIDE_MIN:
                trop_pres.append((d, n1, n2, 'liaison' in paire))
    trop_pres.sort()
    if not trop_pres:
        ctrl(True, f"{nom_page} : tous les objets sont à au moins {num(VIDE_MIN)} mm les uns des autres")
    for d, n1, n2, liaison in trop_pres:
        if liaison:      # page 2 : un trait droit peut frôler une autre sortie ; c'est à savoir, pas une faute du plan
            ctrl(None, f"{nom_page} : la {n1 if n1.startswith('liaison') else n2} passe à {num(round(d, 1))} mm de la "
                 f"{n2 if n1.startswith('liaison') else n1} : au doigt, suivre le trait jusqu'au carré où il s'arrête")
        else:
            ctrl(False if d < 0.5 else None, f"{nom_page} : {n1} et {n2} à {num(round(d, 1))} mm l'un de l'autre"
                 + (" : ils se touchent" if d < 0.5 else f" (moins de {num(VIDE_MIN)} mm : ils risquent de se confondre au toucher)"))


ecarts(objets_p1, 'page 1')
ecarts(objets_p2, 'page 2')
serrees = [f"{s['numero']} et {t['numero']} ({num(round(math.dist(s['xy'], t['xy']), 1))} mm)"
           for i, s in enumerate(sorties) for t in sorties[i + 1:] if math.dist(s['xy'], t['xy']) < R['pas_sorties_min_mm']]
ctrl(None if serrees else True, f"sorties voisines à au moins {num(R['pas_sorties_min_mm'])} mm de centre à centre"
     + (f" — sauf : {', '.join(serrees)}" if serrees else ''))
for i, l1 in enumerate(liaisons):
    for l2 in liaisons[i + 1:]:
        if l1['ligne'].crosses(l2['ligne']):
            ctrl(None, f"page 2 : les liaisons {l1['nom'][8:]} et {l2['nom'][8:]} se croisent : "
                 "au routage, l'une passera sur l'autre face (via)")

# ---------- 6. la légende (même texte en braille et dans la notice), le plus court possible
legende = [f"agrandie {num(S)} fois. sorties : numéros du plan de test et du banc."]
for b in CARTE.blocs:
    et = b.bloc.get('etiquette', b.id).lower()
    for cote in ('haut', 'droite', 'bas', 'gauche'):
        ss = [s for s in sorties if s['bloc'] is b and s['cote'] == cote]
        if not ss:
            continue
        vertical = cote in ('gauche', 'droite')
        ss.sort(key=lambda s: (-s['xy'][1], s['xy'][0]) if vertical else (s['xy'][0], -s['xy'][1]))
        legende.append(f"{et}, {BORD[cote]}, {'de haut en bas' if vertical else 'de gauche à droite'} : "
                       + ', '.join(f"{s['numero']} {nom_court(s['reseau']).lower()}" for s in ss) + '.')
for b in CARTE.blocs:
    pb = [p for p in prises if p['bloc'] is b]
    if not pb:
        continue
    morceaux = []
    for p in pb:
        x0, y0, x1, y1 = p['carte']
        bords = [c for c, v in (('bas', y0), ('gauche', x0), ('haut', CARTE.hauteur - y1), ('droite', CARTE.largeur - x1)) if v < 2.0]
        ou = f"au {BORD[bords[0]]} de la carte" if bords else \
            position_dans((x0 + x1) / 2, (y0 + y1) / 2, b.position[0], b.position[1], b.position[0] + b.taille[0], b.position[1] + b.taille[1])
        morceaux.append(f"{p['genre']} {p['texte']} {ou}")
    legende.append(f"dans {b.bloc.get('etiquette', b.id).lower()} : " + ', '.join(morceaux) + '.')
if trous:
    ou = [position_dans(x, y, 0, 0, CARTE.largeur, CARTE.hauteur) for x, y in (t['xy'] for t in trous)]
    legende.append(f"{len(trous)} trous de fixation : " + ', '.join(f"{ou.count(o)} {o}" for o in dict.fromkeys(ou)) + '.')
for z in zones:
    x0, y0, x1, y1 = z['carte']
    legende.append(f"zone : {z['raison']}, " + position_dans((x0 + x1) / 2, (y0 + y1) / 2, 0, 0, CARTE.largeur, CARTE.hauteur)
                   + " de la carte.")
if liaisons:
    legende.append("page 2 : un trait relie deux sorties de même nom.")
liaisons_texte = [f"{nom_court(l['reseau']).lower()} : sortie {l['a']['numero']} "
                  f"({l['a']['bloc'].bloc.get('etiquette', l['a']['bloc'].id).lower()}) à sortie {l['b']['numero']} "
                  f"({l['b']['bloc'].bloc.get('etiquette', l['b']['bloc'].id).lower()})." for l in liaisons]

pages_legende, courante, y = [], None, None


def nouvelle_page():
    global courante, y
    g, y = bloc_braille(f"{NOM} : légende" + (' (suite)' if pages_legende else ''), M, H - M, W - 2 * M)
    courante = [g]
    pages_legende.append(courante)
    y -= PAS / 2


nouvelle_page()
for texte in legende:
    ls = couper(texte, cellules_max(W - 2 * M))
    if y - len(ls) * PAS < M:
        nouvelle_page()
    g, y = bloc_braille(texte, M, y, W - 2 * M)
    courante.append(g)
    y -= 2
ctrl(True, f"légende en braille : {len(legende)} paragraphes sur {len(pages_legende)} page(s)")


# ---------- 7. dessin : le noir en polygones exacts ; le bleu ne gonfle pas
def polygones(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type == 'Polygon':
        return [g]
    return [p for x in getattr(g, 'geoms', []) for p in polygones(x)]


def chemin(geom):
    verts, codes = [], []
    for p in polygones(geom):
        p = orient(p, 1.0)
        for anneau in [p.exterior, *p.interiors]:
            xy = list(anneau.coords)
            verts += xy
            codes += [Path.MOVETO] + [Path.LINETO] * (len(xy) - 2) + [Path.CLOSEPOLY]
    return Path(verts, codes) if verts else None


def page(noir, bleus):
    fig = plt.figure(figsize=(W / 25.4, H / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect('equal')
    ax.axis('off')
    ch = chemin(noir)
    if ch is not None:
        ax.add_patch(PathPatch(ch, facecolor='black', edgecolor='none', lw=0))
    for x, yy, txt in bleus:
        ax.text(x, yy, txt, color=BLEU, fontsize=HT * 72 / 25.4 / 0.72, va='top')
    return fig


noirs = [unary_union([col1, contour] + [bl['geom'] for bl in blocs] + [s['geom'] for s in sorties] + [p['geom'] for p in prises]
                     + [t['geom'] for t in trous] + [z['geom'] for z in zones] + noms1),
         unary_union([col2, contour] + [bl['geom'] for bl in blocs] + [l['geom'] for l in liaisons] + [s['geom'] for s in sorties] + noms2)]
bleus = [bleus1, bleus2]
for i, pl in enumerate(pages_legende):
    noirs.append(unary_union(pl))
    bleus.append([(M, M / 2 + 1.5, f"{CARTE.nom} — page {3 + i} : légende en braille — le bleu ne gonfle pas")])
pdf = os.path.join(DOSSIER, 'plan-tactile.pdf')
with PdfPages(pdf) as doc:
    for i, (noir, bl) in enumerate(zip(noirs, bleus), 1):
        fig = page(noir, bl)
        doc.savefig(fig)
        fig.savefig(os.path.join(DOSSIER, f'plan-tactile-page-{i}.svg'))
        fig.savefig(os.path.join(DOSSIER, f'plan-tactile-page-{i}.png'), dpi=100)
        plt.close(fig)
hors = [i + 1 for i, noir in enumerate(noirs) if not box(M - 0.01, M - 0.01, W - M + 0.01, H - M + 0.01).contains(noir)]
ctrl(not hors, "tout le noir est dans les marges de la page" + (f" — sauf page(s) {hors}" if hors else ''))

# ---------- 8. notice (texte, pour le lecteur d'écran) et bilan
n_leg = len(pages_legende)
notice = [f"PLAN À TOUCHER SUR PAPIER GONFLÉ — {CARTE.nom}",
          f"Fait par la chaîne puzzle (plan_tactile.py) le {time.strftime('%d/%m/%Y')}, d'après {os.path.basename(CARTE.fichier)} : "
          "la disposition des blocs, avant routage.", '',
          "== Ce que c'est ==",
          f"Un plan de la carte agrandie {num(S)} fois ({S * CARTE.largeur:.0f} × {S * CARTE.hauteur:.0f} mm), à imprimer sur "
          "papier gonflé : ce qui est noir gonfle sous la chaleur et se lit au doigt. Il sert à sentir la disposition des blocs "
          "en quelques minutes, avant de router. La maquette 3D reste le modèle détaillé.",
          "Page 1 : la carte. Page 2 : les liaisons entre blocs. "
          + (f"Page 3 : la légende en braille." if n_leg == 1 else f"Pages 3 à {2 + n_leg} : la légende en braille."),
          "Le haut de la feuille est le haut de la carte. Sur les pages 1 et 2, la colonne de gauche donne le titre en braille, "
          "puis la clé des symboles : chaque symbole, suivi de son nom en un mot de braille.", '',
          '== Imprimer ==',
          f"- plan-tactile.pdf, {R['papier']['nom']}, à 100 % (taille réelle : ne pas « ajuster à la page »), sur papier gonflé, côté traité.",
          "- Le noir doit être à base de carbone : c'est lui qui gonfle. Le texte bleu, pour les personnes qui voient, ne gonfle pas "
          "avec une imprimante à jet d'encre couleur ; une photocopieuse le rendrait noir.",
          "- Passer la feuille dans la machine à papier gonflé (PIAF, Zychem…).",
          "- Les épaisseurs n'ont pas encore été essayées sur du vrai papier gonflé : noter ce qui gonfle trop ou pas assez, "
          "pour ajuster bibliotheque/regles/plan_tactile.json.",
          "- Les images plan-tactile-page-N.svg se retouchent dans Inkscape ; les .png servent à vérifier.", '',
          '== Symboles (mot de la clé : dessin, ce que c\'est) ==']
notice += [f"- « {SYMBOLES[g][0]} » : {SYMBOLES[g][1]}, {SYMBOLES[g][2]}." for g in dict.fromkeys(genres1 + genres2)]
notice += ["- Le bord d'un bloc s'interrompt là où il longe le bord de la carte, et là où un objet le touche presque.",
           "- Page 2 : chaque liaison est un trait droit d'une sortie à l'autre, comme le « chevelu » de KiCad avant routage. "
           "Ce n'est pas le chemin de la vraie piste, qui contourne les blocs.",
           '', "== Légende (la même qu'en braille) =="]
notice += [f"- {l[0].upper() + l[1:]}" for l in legende]
if liaisons_texte:
    notice += ['', "== Liaisons de la page 2 (dans la notice seulement : trop long pour la légende braille) =="]
    notice += [f"- {l[0].upper() + l[1:]}" for l in liaisons_texte]
notice += ['', '== Contrôles ==']
notice += controles
notice += ['', "Règles chiffrées et leurs sources : bibliotheque/regles/plan_tactile.json."]
open(os.path.join(DOSSIER, 'plan-tactile.txt'), 'w', encoding='utf-8').write('\n'.join(notice) + '\n')
print(f"Plan à toucher : {pdf} ({len(noirs)} pages, carte agrandie {num(S)} fois)")
for c in controles:
    print('  ' + c)
sys.exit(1 if any(c.startswith('✗') for c in controles) else 0)
