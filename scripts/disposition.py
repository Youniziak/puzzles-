"""Chaîne puzzle, étape 0 — contrôle de la disposition des blocs, en quelques secondes, avant tout routage.
Sans KiCad : seulement le fichier de la carte et ceux des blocs.
  1. chaque bloc tient dans la carte, sans en chevaucher un autre (déjà vérifié à la lecture) ;
  2. chaque sortie d'un bloc (pastille de bord) est tournée vers l'intérieur de la carte, pas vers le bord ;
  3. chaque sortie a au moins une sortie partenaire (même réseau, autre bloc) devant elle :
     sinon la liaison devra faire le tour du bloc ;
  4. ce qui doit être au bord de la carte (prises, antenne : « au_bord » dans bloc.json) y est bien.
Usage : python3 disposition.py cartes/ma-carte.json   (code de sortie 1 s'il y a une erreur)"""
import sys
from description import Carte, ROTATIONS

CARTE = Carte(sys.argv[1])
TOL = 1.0                       # mm : un côté de bloc à moins de 1 mm du bord de la carte est « au bord »
COTES = {'gauche': (-1, 0), 'droite': (1, 0), 'bas': (0, -1), 'haut': (0, 1)}
NOM_COTE = {v: k for k, v in COTES.items()}

def cote_sur_carte(b, cote_local):
    """Côté local du bloc (gauche, droite, bas, haut) → côté sur la carte, une fois le bloc tourné."""
    nx, ny = ROTATIONS[b.rotation](*COTES[cote_local])
    return NOM_COTE[(round(nx), round(ny))]

def au_bord(b, cote):
    x0, y0 = b.position
    x1, y1 = x0 + b.taille[0], y0 + b.taille[1]
    return {'gauche': x0 <= TOL, 'droite': x1 >= CARTE.largeur - TOL, 'bas': y0 <= TOL, 'haut': y1 >= CARTE.hauteur - TOL}[cote]

erreurs, avertissements = [], []

# Sorties : position sur la carte et côté du bloc vers lequel elles sont tournées (le bord du bloc le plus proche)
sorties = []      # (bloc, repère, réseau, (x, y), côté sur la carte)
for b in CARTE.blocs:
    w, h = b.design['board']['width'], b.design['board']['height']
    for p in b.design['parts']:
        if p['id'] not in b.bloc.get('non_poses', []):
            continue
        reseaux = {CARTE.reseau(b, q.get('netName')) for q in p['pads']} - {None}
        dist = {'gauche': p['x'], 'droite': w - p['x'], 'bas': p['y'], 'haut': h - p['y']}
        cote = cote_sur_carte(b, min(dist, key=dist.get))
        for n in reseaux:
            sorties.append((b, CARTE.repere(b, p['id']), n, b.point(p['x'], p['y']), cote))

print("== Sorties des blocs ==")
for b, ref, n, (x, y), cote in sorties:
    if au_bord(b, cote):
        erreurs.append(f"la sortie {ref} ({n}) du bloc {b.id} est tournée vers le bord de la carte ({cote}) : rien ne pourra la rejoindre de ce côté")
        continue
    partenaires = [(pb, pr, (px, py)) for pb, pr, pn, (px, py), _ in sorties if pn == n and pb is not b]
    if not partenaires:
        continue
    nx, ny = COTES[cote]
    devant = [pr for pb, pr, (px, py) in partenaires if (px - x) * nx + (py - y) * ny > 0]
    if not devant:
        avertissements.append(f"la sortie {ref} ({n}) du bloc {b.id} regarde vers {cote}, mais ses partenaires "
                              f"({', '.join(pr for _, pr, _ in partenaires)}) sont derrière : la liaison devra faire le tour du bloc")
print(f"  {len(sorties)} sorties examinées")

print("== Ce qui doit être au bord de la carte ==")
for b in CARTE.blocs:
    for a in b.bloc.get('au_bord', []):
        cote = cote_sur_carte(b, a['cote'])
        etat = au_bord(b, cote)
        print(f"  {'✓' if etat else '✗'} {b.id} : {a['quoi']} — côté {cote} de la carte")
        if not etat:
            erreurs.append(f"{a['quoi']} (bloc {b.id}) devrait être au bord de la carte, côté {cote}, mais le bloc n'y touche pas")

if CARTE.trou:
    print("== Trous de fixation ==")
    trous = CARTE.trous_fixation
    for i, (x, y) in enumerate(trous, 1):
        print(f"  H{i} en ({x:g} ; {y:g}) mm, hors des blocs" + (", relié à la masse" if CARTE.trou['masse'] else ''))
    if len(trous) < CARTE.trou['nombre']:
        avertissements.append(f"{len(trous)} trou(s) de fixation trouvé(s) sur {CARTE.trou['nombre']} demandés : pas assez de place libre hors des blocs")
    if not trous:
        erreurs.append("aucune place libre pour un trou de fixation : agrandir la carte ou donner les positions")

print("== Bilan de la disposition ==")
for e in erreurs:
    print("  ✗", e)
for a in avertissements:
    print("  ⚠", a)
if not erreurs and not avertissements:
    print("  ✓ rien à redire")
elif not erreurs:
    print(f"  {len(avertissements)} avertissement(s), aucune erreur : on peut router")
sys.exit(1 if erreurs else 0)
