"""Chaîne puzzle, étape 3 bis — schéma KiCad lisible par un humain, tiré de la carte assemblée.
Un cadre par bloc, les vrais symboles des composants (easyeda2kicad, bibliotheque/empreintes/*.kicad_sym),
et sur chaque broche une étiquette au nom de la liaison (c'est ainsi que KiCad relie les broches entre elles).
Broche sans liaison : croix « non connectée ». Pas de fils tracés : le schéma reste lisible et juste par construction.
Les étiquettes sont globales : la liaison s'appelle « VBUS » comme sur la carte (une étiquette locale donnerait « /VBUS »).
Les broches reçoivent leur vrai type (entrée, sortie, alimentation…) d'après bibliotheque/empreintes/types-broches.json
(fait par outils/typer_broches.py, depuis la bibliothèque officielle de KiCad) : sans cela, l'ERC est presque aveugle.
Un drapeau d'alimentation (PWR_FLAG) dit à KiCad quelles liaisons sont alimentées depuis l'extérieur : la masse, et les
liaisons de « alimentations_externes » dans la carte (par exemple le VBUS de la prise USB).
Puis KiCad le contrôle et l'exporte :
  - contrôle électrique (ERC), avertissements compris ;
  - export PDF (schema.pdf), pour la relecture ;
  - comparaison liaison par liaison entre le schéma et la carte (liste des réseaux exportée par KiCad) ;
  - parité schéma ↔ carte par KiCad lui-même (kicad-cli pcb drc --schematic-parity) : liaisons, et champs des composants
    (référence LCSC, fabricant, MPN), ce qui attrape une référence LCSC fausse sur une empreinte.
Usage : python3 schema.py cartes/ma-carte.json dossier_projet/carte.kicad_pcb"""
import json, math, os, re, subprocess, sys, uuid
from collections import defaultdict
import pcbnew
from description import Carte
from sexpr import lire_sexpr, ecrire_sexpr, q, broches as broches_de, numero_nom
from description import champs_piece as CHAMPS

CARTE = Carte(sys.argv[1])
PCB = sys.argv[2]
PROJET = os.path.dirname(os.path.abspath(PCB))
SCH = os.path.join(PROJET, 'carte.kicad_sch')
G = 1.27                                         # grille de KiCad pour les schémas
ESPACE = 'b5a1e5c2-7b1f-4d0e-9c1a-5c4b0e0a1f00'  # pour des identifiants stables d'une fois sur l'autre
def uid(*cles):
    return str(uuid.uuid5(uuid.UUID(ESPACE), '/'.join(map(str, cles))))
RACINE = uid(CARTE.nom, 'racine')

# ---------- lecture de la bibliothèque de symboles (expressions S de KiCad : voir sexpr.py)
fichier_sym = next(os.path.join(CARTE.empreintes, f) for f in os.listdir(CARTE.empreintes) if f.endswith('.kicad_sym'))
NOM_BIB = os.path.splitext(os.path.basename(fichier_sym))[0]
bib = lire_sexpr(open(fichier_sym, encoding='utf-8').read())
NON_POSES = {CARTE.repere(b, r) for b in CARTE.blocs for r in b.bloc.get('non_poses', [])}   # sorties en cuivre nu, hors liste des pièces
SYMBOLES = {}                                     # numéro LCSC → définition
for s in bib:
    if isinstance(s, list) and s and s[0] == 'symbol':
        lcsc = next((p[2].strip('"') for p in s if isinstance(p, list) and p[:2] == ['property', '"LCSC Part"']), None)
        if lcsc:
            SYMBOLES[lcsc] = s
f_types = os.path.join(CARTE.empreintes, 'types-broches.json')
TYPES = json.load(open(f_types, encoding='utf-8'))['pieces'] if os.path.exists(f_types) else {}
non_types = []
for lcsc, s in SYMBOLES.items():
    t_lcsc = TYPES.get(lcsc, {}).get('broches', {})
    for pin in broches_de(s):
        num, nom = numero_nom(pin)
        if num in t_lcsc:
            pin[1] = t_lcsc[num]['type']
        elif pin[1] == 'unspecified':
            non_types.append(f"{lcsc}.{num}")
PWR_FLAG = lire_sexpr('''(symbol "PWR_FLAG" (power) (pin_numbers hide) (pin_names (offset 0) hide) (in_bom no) (on_board yes)
  (property "Reference" "#FLG" (id 0) (at 0 3.81 0) (effects (font (size 1.27 1.27)) hide))
  (property "Value" "PWR_FLAG" (id 1) (at 0 5.08 0) (effects (font (size 1.27 1.27))))
  (property "Footprint" "" (id 2) (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
  (property "Datasheet" "~" (id 3) (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
  (symbol "PWR_FLAG_0_0" (pin power_out line (at 0 0 90) (length 0) (name "pwr" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27))))))
  (symbol "PWR_FLAG_0_1" (polyline (pts (xy 0 0) (xy 0 1.27) (xy -1.016 1.905) (xy 0 2.54) (xy 1.016 1.905) (xy 0 1.27)) (stroke (width 0) (type default)) (fill (type none)))))''')
bib.append(PWR_FLAG)

def geometrie(s):
    """Broches (numéro, x, y, angle, longueur, nom) et cadre du dessin, coordonnées de la bibliothèque (y vers le haut)."""
    broches, pts = [], []
    def parcours(e):
        for x in e:
            if not isinstance(x, list):
                continue
            if x[0] == 'pin':
                at = next(a for a in x if isinstance(a, list) and a[0] == 'at')
                lg = next((float(a[1]) for a in x if isinstance(a, list) and a[0] == 'length'), 2.54)
                num = next(a[1].strip('"') for a in x if isinstance(a, list) and a[0] == 'number')
                nom = next(a[1].strip('"') for a in x if isinstance(a, list) and a[0] == 'name')
                broches.append((num, float(at[1]), float(at[2]), int(float(at[3])) % 360, lg, nom))
            elif x[0] in ('rectangle', 'polyline', 'circle', 'arc'):
                for y in x:
                    if isinstance(y, list) and y[0] in ('start', 'end', 'center', 'mid'):
                        pts.append((float(y[1]), float(y[2])))
                    if isinstance(y, list) and y[0] == 'pts':
                        pts.extend((float(z[1]), float(z[2])) for z in y if isinstance(z, list) and z[0] == 'xy')
                    if x[0] == 'circle' and isinstance(y, list) and y[0] == 'radius':
                        r = float(y[1]); cx, cy = pts[-1]; pts.extend([(cx - r, cy - r), (cx + r, cy + r)])
            else:
                parcours(x)
    parcours(s)
    for _, x, y, a, lg, _ in broches:
        pts.append((x, y))
    xs, ys = [p[0] for p in pts] or [0], [p[1] for p in pts] or [0]
    return broches, (min(xs), min(ys), max(xs), max(ys))

# ---------- la carte assemblée : pour chaque composant, le réseau de chaque pastille
board = pcbnew.LoadBoard(PCB)
fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
TAILLE_TEXTE = 1.27
BOUT = 2.54            # petit fil entre la broche et son étiquette, pour ne pas écrire sur le numéro de broche
DEHORS = {0: (-1, 0), 180: (1, 0), 90: (0, -1), 270: (0, 1)}   # direction qui s'éloigne du symbole (bibliothèque, y vers le haut)
def long_etiquette(t):
    return len(t) * TAILLE_TEXTE * 0.85 + 1.5

def etiquette_globale(nom, x, y, angle, just, ident):
    return (f'(global_label {q(nom)} (shape passive) (at {x:.2f} {y:.2f} {angle}) (fields_autoplaced yes) '
            f'(effects (font (size 1.27 1.27)) (justify {just})) (uuid {q(ident)}) '
            f'(property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {x:.2f} {y:.2f} 0) (effects (font (size 1.27 1.27)) (hide yes))))')

composants = []           # par bloc : (repère, lcsc, valeur, réseaux par numéro de pastille)
manques = []
for b in CARTE.blocs:
    liste = []
    for p in b.design['parts']:
        ref = CARTE.repere(b, p['id'])
        fp = fps.get(ref)
        if fp is None or p['lcscPartNumber'] not in SYMBOLES:
            manques.append(f"{ref} ({p['lcscPartNumber']})"); continue
        reseaux = defaultdict(set)
        for pad in fp.Pads():
            if pad.GetNumber():
                reseaux[pad.GetNumber()].add(pad.GetNetname())
        liste.append((ref, p['lcscPartNumber'], fp.GetValue() or p.get('value', ''), fp.GetFPIDAsString(), reseaux, p))
    composants.append((b, liste))

# ---------- disposition : chaque bloc dans un cadre, ses composants rangés en rangées
def encombrement(lcsc, reseaux):
    broches, (x0, y0, x1, y1) = geometrie(SYMBOLES[lcsc])
    for num, x, y, a, lg, nom in broches:
        n = next(iter(reseaux.get(num, {''})), '')
        L = long_etiquette(n) + BOUT if n else 1.5
        if a == 0: x0 = min(x0, x - L)
        elif a == 180: x1 = max(x1, x + L)
        elif a == 90: y0 = min(y0, y - L)
        else: y1 = max(y1, y + L)
    return x0 - 2.54, y0 - 3.5, x1 + 2.54, y1 + 3.5       # place pour le repère et la valeur

MARGE = 10.16
import textwrap
contenus = []             # par bloc : (bloc, largeur, hauteur, lignes de description, [(composant, ox, oy)])
for b, liste in composants:
    # les puces et les prises d'abord, les petits composants ensuite, les sorties à la fin
    non_poses = {CARTE.repere(b, r) for r in b.bloc.get('non_poses', [])}
    ordre = lambda r: [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', r)]   # TP9 avant TP10
    liste.sort(key=lambda c: (c[0] in non_poses, -len(geometrie(SYMBOLES[c[1]])[0]), ordre(c[0])))
    tailles = [encombrement(c[1], c[4]) for c in liste]
    aire = sum((t[2] - t[0]) * (t[3] - t[1]) for t in tailles)
    largeur = max(max(t[2] - t[0] for t in tailles) + 2 * G, math.sqrt(aire) * 1.15, 90)
    lignes = textwrap.wrap(b.bloc.get('description', ''), int(largeur / (1.27 * 0.95)))
    titre = 9 + 2.2 * len(lignes) + 3
    x, y, haut_rangee, pos = 0.0, titre, 0.0, []
    for c, (x0, y0, x1, y1) in zip(liste, tailles):
        w, h = x1 - x0, y1 - y0
        if x > 0 and x + w > largeur:
            x, y, haut_rangee = 0.0, y + haut_rangee, 0.0
        # origine du symbole : coin du rectangle d'encombrement, sur la grille ; y de la feuille vers le bas
        ox = round((x - x0) / G) * G; oy = round((y + y1) / G) * G
        pos.append((c, ox, oy))
        x += w; haut_rangee = max(haut_rangee, h)
    contenus.append((b, largeur, y + haut_rangee, lignes, pos))

# Les blocs en colonnes : on essaie 1, 2, 3… colonnes et on garde la plus petite feuille qui contient tout
FORMATS = [('A4', 297, 210), ('A3', 420, 297), ('A2', 594, 420), ('A1', 841, 594), ('A0', 1189, 841)]
BAS = 40                  # place du cartouche, en bas de la feuille
def ranger(k):
    colonnes = [[] for _ in range(k)]
    for c in sorted(contenus, key=lambda c: -c[2]):
        min(colonnes, key=lambda col: sum(x[2] + 2 * MARGE for x in col)).append(c)
    colonnes = [col for col in colonnes if col]
    largeur = 2 * MARGE + sum(max(c[1] for c in col) + 2 * MARGE for col in colonnes)
    hauteur = 2 * MARGE + max(sum(c[2] + 2 * MARGE for c in col) for col in colonnes) + BAS
    rang = next((i for i, (n, w, h) in enumerate(FORMATS) if largeur <= w and hauteur <= h), len(FORMATS))
    return (rang, largeur * hauteur), colonnes, largeur, hauteur
_, colonnes, W_FEUILLE, H_FEUILLE = min((ranger(k) for k in range(1, len(contenus) + 1)), key=lambda r: r[0])
places = []
x_col = 2 * MARGE
for col in colonnes:
    y_bloc = 2 * MARGE
    for b, largeur, hauteur, lignes, pos in col:
        places.append((b, (x_col, y_bloc, x_col + largeur, y_bloc + hauteur), lignes, pos))
        y_bloc += hauteur + 2 * MARGE
    x_col += max(c[1] for c in col) + 2 * MARGE
papier = next((f'"{n}"' for n, w, h in FORMATS if W_FEUILLE <= w and H_FEUILLE <= h), None)
if papier is None:
    papier = f'"User" {math.ceil(W_FEUILLE)} {math.ceil(H_FEUILLE)}'

# ---------- écriture du schéma
lib_symbols, utilises = [], set()
objets = []
for b, (bx0, by0, bx1, by1), lignes, pos in places:
    objets.append(f'(rectangle (start {bx0 - G * 2:.2f} {by0 - G:.2f}) (end {bx1 + G * 2:.2f} {by1 + G:.2f}) '
                  f'(stroke (width 0.3) (type dash)) (fill (type none)) (uuid {q(uid(b.id, "cadre"))}))')
    objets.append(f'(text {q("Bloc " + b.id + " — " + b.bloc.get("etiquette", ""))} (exclude_from_sim no) (at {bx0:.2f} {by0 + 3:.2f} 0) '
                  f'(effects (font (size 2.54 2.54) (thickness 0.5) bold) (justify left bottom)) (uuid {q(uid(b.id, "titre"))}))')
    for i, ligne in enumerate(lignes):
        objets.append(f'(text {q(ligne)} (exclude_from_sim no) (at {bx0:.2f} {by0 + 7 + 2.2 * i:.2f} 0) '
                      f'(effects (font (size 1.27 1.27)) (justify left bottom)) (uuid {q(uid(b.id, "desc", i))}))')
    for (ref, lcsc, valeur, empreinte, reseaux, piece), ox, oy in pos:
        X, Y = bx0 + ox, by0 + oy
        X, Y = round(X / G) * G, round(Y / G) * G
        s = SYMBOLES[lcsc]; nom_sym = s[1].strip('"')
        if nom_sym not in utilises:
            utilises.add(nom_sym)
            copie = [x for x in s if not (isinstance(x, list) and x and x[0] == 'property' and False)]
            copie = ['symbol', q(f'{NOM_BIB}:{nom_sym}')] + [
                [y for y in x if not (isinstance(y, list) and y and y[0] == 'id')] if isinstance(x, list) and x and x[0] == 'property' else x
                for x in s[2:]]
            lib_symbols.append(ecrire_sexpr(copie, 1))
        broches, (sx0, sy0, sx1, sy1) = geometrie(s)
        ex0, ey0, ex1, ey1 = encombrement(lcsc, reseaux)
        su = uid(CARTE.nom, ref)
        props = (f'(property "Reference" {q(ref)} (at {X + sx0:.2f} {Y - ey1 + 2.0:.2f} 0) (effects (font (size 1.27 1.27)) (justify left)))\n'
                 f'    (property "Value" {q(valeur)} (at {X + sx0:.2f} {Y - ey0 - 1.0:.2f} 0) (effects (font (size 1.27 1.27)) (justify left)))\n'
                 f'    (property "Footprint" {q(empreinte)} (at {X:.2f} {Y:.2f} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
                 f'    (property "LCSC Part" {q(lcsc)} (at {X:.2f} {Y:.2f} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
        for champ, v in CHAMPS(piece):                 # les mêmes valeurs que sur l'empreinte (assembler.py) : la parité les compare
            if champ != 'LCSC Part':
                props += f'\n    (property {q(champ)} {q(v)} (at {X:.2f} {Y:.2f} 0) (effects (font (size 1.27 1.27)) (hide yes)))'
        pins = '\n'.join(f'    (pin {q(num)} (uuid {q(uid(su, "pin", num, i))}))' for i, (num, *_r) in enumerate(broches))
        objets.append(f'(symbol (lib_id {q(NOM_BIB + ":" + nom_sym)}) (at {X:.2f} {Y:.2f} 0) (unit 1) (exclude_from_sim no) '
                      f'(in_bom {"no" if ref in NON_POSES else "yes"}) (on_board yes) (dnp no) (uuid {q(su)})\n    {props}\n{pins}\n'
                      f'    (instances (project "carte" (path {q("/" + RACINE)} (reference {q(ref)}) (unit 1)))))')
        deja = set()
        for num, px, py, a, lg, nom in broches:
            cx, cy = X + px, Y - py                    # point de connexion sur la feuille (y vers le bas)
            if (num, round(cx, 3), round(cy, 3)) in deja:
                continue
            deja.add((num, round(cx, 3), round(cy, 3)))
            noms = sorted(n for n in reseaux.get(num, set()) if n)
            if not noms:
                objets.append(f'(no_connect (at {cx:.2f} {cy:.2f}) (uuid {q(uid(su, "nc", num, cx, cy))}))')
                continue
            angle, just = {0: (180, 'right'), 180: (0, 'left'), 90: (270, 'right'), 270: (90, 'left')}[a]
            dx, dy = DEHORS[a]
            fx, fy = cx + dx * BOUT, cy - dy * BOUT
            objets.append(f'(wire (pts (xy {cx:.2f} {cy:.2f}) (xy {fx:.2f} {fy:.2f})) (stroke (width 0) (type default)) (uuid {q(uid(su, "fil", num, cx, cy))}))')
            cx, cy = fx, fy
            objets.append(etiquette_globale(noms[0], cx, cy, angle, just, uid(su, "lab", num, cx, cy)))

alim_ext = [CARTE.masse] + [n for n in CARTE.donnees.get('alimentations_externes', []) if n != CARTE.masse]
lib_symbols.append(ecrire_sexpr(['symbol', q(f'{NOM_BIB}:PWR_FLAG')] + [
    [y for y in x if not (isinstance(y, list) and y and y[0] == 'id')] if isinstance(x, list) and x and x[0] == 'property' else x
    for x in PWR_FLAG[2:]], 1))
for i, n in enumerate(alim_ext):
    fx, fy = round((2 * MARGE + 30 * i) / G) * G, round((H_FEUILLE - BAS + 22) / G) * G
    su = uid(CARTE.nom, 'drapeau', n)
    objets.append(f'(symbol (lib_id {q(NOM_BIB + ":PWR_FLAG")}) (at {fx:.2f} {fy:.2f} 0) (unit 1) (exclude_from_sim no) (in_bom no) (on_board yes) (dnp no) (uuid {q(su)})\n'
                  f'    (property "Reference" {q(f"#FLG0{i + 1}")} (at {fx:.2f} {fy - 3.81:.2f} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
                  f'    (property "Value" "PWR_FLAG" (at {fx:.2f} {fy - 5.08:.2f} 0) (effects (font (size 1.27 1.27))))\n'
                  f'    (property "Footprint" "" (at {fx:.2f} {fy:.2f} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
                  f'    (property "Datasheet" "~" (at {fx:.2f} {fy:.2f} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
                  f'    (pin "1" (uuid {q(uid(su, "pin"))}))\n'
                  f'    (instances (project "carte" (path {q("/" + RACINE)} (reference {q(f"#FLG0{i + 1}")}) (unit 1)))))')
    objets.append(etiquette_globale(n, fx, fy, 270, 'right', uid(su, 'lab')))
trous = sorted(r for r, fp in fps.items() if fp.GetAttributes() & pcbnew.FP_BOARD_ONLY)
if trous:
    objets.append(f'(text {q("Trous de fixation " + ", ".join(trous) + " : sur la carte seulement" + (" (reliés à la masse)" if CARTE.trou and CARTE.trou["masse"] else ""))} '
                  f'(exclude_from_sim no) (at {2 * MARGE:.2f} {H_FEUILLE - BAS + 8:.2f} 0) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid {q(uid("trous"))}))')
entete = (f'(kicad_sch (version 20231120) (generator "chaine_puzzle") (generator_version "1.6") (uuid {q(RACINE)}) (paper {papier})\n'
          f'  (title_block (title {q(CARTE.nom)}) (date "{__import__("datetime").date.today().isoformat()}") (rev "chaîne puzzle")'
          f' (company "Exylia Project") (comment 1 "Schéma produit par la chaîne puzzle à partir de la carte : une étiquette = une liaison"))\n')
texte = entete + '  (lib_symbols\n    ' + '\n    '.join(lib_symbols) + ')\n  ' + '\n  '.join(objets) + \
        '\n  (sheet_instances (path "/" (page "1"))))\n'
open(SCH, 'w', encoding='utf-8').write(texte)
open(os.path.join(PROJET, 'sym-lib-table'), 'w').write(
    f'(sym_lib_table\n  (version 7)\n  (lib (name "{NOM_BIB}")(type "KiCad")(uri "${{KIPRJMOD}}/lib/{NOM_BIB}.kicad_sym")(options "")(descr "Symboles LCSC via easyeda2kicad"))\n)\n')
os.makedirs(os.path.join(PROJET, 'lib'), exist_ok=True)
open(os.path.join(PROJET, 'lib', NOM_BIB + '.kicad_sym'), 'w', encoding='utf-8').write(ecrire_sexpr(bib) + '\n')
print(f"Schéma : {SCH} — feuille {papier.split()[0].strip(chr(34))}, {sum(len(p) for _, _, _, p in places)} symboles"
      + (f" ; sans symbole : {', '.join(manques)}" if manques else ''))
print(f"Types des broches : {'types-broches.json appliqué' if TYPES else 'types-broches.json absent : ERC presque aveugle'}"
      + (f" ; {len(non_types)} broche(s) sans type : {', '.join(non_types[:10])}" if non_types else " ; toutes les broches ont un type")
      + f" ; drapeaux d'alimentation : {', '.join(alim_ext)}")

# ---------- contrôles par KiCad : ERC, PDF, et comparaison schéma ↔ carte
def kicad(*args):
    return subprocess.run(['kicad-cli', *args], capture_output=True, text=True)
kicad('sch', 'erc', '--format', 'json', '--severity-all', '--output', os.path.join(PROJET, 'schema-erc.json'), SCH)
erc = json.load(open(os.path.join(PROJET, 'schema-erc.json')))
toutes = [v for s in erc.get('sheets', []) for v in s.get('violations', [])]
erreurs = [v for v in toutes if v.get('severity') == 'error']
avertissements = [v for v in toutes if v.get('severity') != 'error']
from collections import Counter
print('Contrôle électrique (ERC) :', (str(dict(Counter(v['type'] for v in erreurs))) if erreurs else 'aucune erreur') + ' ; avertissements : '
      + (str(dict(Counter(v['type'] for v in avertissements))) if avertissements else 'aucun'))
for v in erreurs[:15] + avertissements[:10]:
    print('   ' + ('✗' if v in erreurs else '⚠'), v.get('description', ''), '—', ' / '.join(i.get('description', '') for i in v.get('items', [])[:3]))
kicad('sch', 'export', 'pdf', '--output', os.path.join(PROJET, 'schema.pdf'), SCH)
print('PDF :', os.path.join(PROJET, 'schema.pdf'))

kicad('sch', 'export', 'netlist', '--format', 'kicadsexpr', '--output', os.path.join(PROJET, 'schema.net'), SCH)
net = lire_sexpr(open(os.path.join(PROJET, 'schema.net'), encoding='utf-8').read())
du_schema = {}
for bloc in net:
    if isinstance(bloc, list) and bloc[0] == 'nets':
        for n in bloc[1:]:
            nom = next(x[1].strip('"') for x in n if isinstance(x, list) and x[0] == 'name')
            for x in n:
                if isinstance(x, list) and x[0] == 'node':
                    ref = next(y[1].strip('"') for y in x if isinstance(y, list) and y[0] == 'ref')
                    pin = next(y[1].strip('"') for y in x if isinstance(y, list) and y[0] == 'pin')
                    du_schema[(ref, pin)] = nom.lstrip('/')
ecarts = []
for ref, fp in fps.items():
    if fp.GetAttributes() & pcbnew.FP_BOARD_ONLY:          # trous de fixation : sur la carte seulement, comme KiCad le prévoit
        continue
    for pad in fp.Pads():
        if not pad.GetNumber() or not pad.GetNetname():
            continue
        s = du_schema.get((ref, pad.GetNumber()))
        if s is None:
            ecarts.append(f'{ref}.{pad.GetNumber()} ({pad.GetNetname()}) : absente du schéma')
        elif not s.startswith('unconnected') and s != pad.GetNetname():
            ecarts.append(f'{ref}.{pad.GetNumber()} : {pad.GetNetname()} sur la carte, {s} sur le schéma')
ecarts = sorted(set(ecarts))
print('Schéma ↔ carte :', 'identiques, liaison par liaison' if not ecarts else f'{len(ecarts)} écart(s) : ' + ' ; '.join(ecarts[:12]))
kicad('pcb', 'drc', '--schematic-parity', '--severity-all', '--format', 'json', '--output', os.path.join(PROJET, 'parite.json'), PCB)
parite = json.load(open(os.path.join(PROJET, 'parite.json'))).get('schematic_parity', [])
non_reliees = [v for v in parite if v['type'] == 'net_conflict' and 'given by schematic (unconnected-' in v.get('description', '')]
parite = [v for v in parite if v not in non_reliees]   # broche libre : « unconnected-… » au schéma, pastille sans liaison sur la carte
print('Parité schéma ↔ carte (KiCad) :', ('rien à redire' if not parite else f'{len(parite)} écart(s) : ' + ' ; '.join(
      f"{' / '.join(i.get('description', '') for i in v.get('items', [])[:1])} : {v.get('description', '')}" for v in parite[:12]))
      + f' ({len(non_reliees)} broches libres, même chose des deux côtés)')
sys.exit(1 if (erreurs or ecarts or manques or parite) else 0)
