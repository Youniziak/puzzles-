"""Broches d'un microcontrôleur ESP32, lues dans la liste des liaisons que KiCad tire du schéma de la chaîne (schema.net).
Écrit un fichier d'en-tête C (broches.h) pour le logiciel : un nom par liaison, et le numéro de GPIO. Rien n'est recopié
à la main : si la carte change, on relance ce script et le programme d'essai suit.
Usage : python3 broches_esp32.py dossier_projet/schema.net sortie/broches.h"""
import re, sys, time


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
    return next((x for x in e if isinstance(x, list) and x and x[0] == nom), None)


NET, SORTIE = sys.argv[1], sys.argv[2]
arbre = lire(open(NET, encoding='utf-8').read())
valeurs = {champ(c, 'ref')[1]: champ(c, 'value')[1] for c in champ(arbre, 'components')[1:]}
puces = [r for r, v in valeurs.items() if 'ESP32' in v.upper()]
if len(puces) != 1:
    sys.exit(f"il faut un seul ESP32 dans le schéma, trouvé : {puces or 'aucun'}")
U = puces[0]
broches = {}
for n in champ(arbre, 'nets')[1:]:
    nom = champ(n, 'name')[1].lstrip('/')
    if nom.startswith('unconnected') or nom in ('GND', '3V3', 'EN'):
        continue
    for x in n:
        if isinstance(x, list) and x[0] == 'node' and champ(x, 'ref')[1] == U:
            m = re.match(r'G?P?IO(\d+)', (champ(x, 'pinfunction') or ['', ''])[1])
            if m:
                broches[re.sub(r'\W', '_', nom).upper()] = int(m.group(1))
lignes = ['// Broches de l\'ESP32 (' + valeurs[U] + ', ' + U + '), écrites par la chaîne puzzle (broches_esp32.py) le '
          + time.strftime('%d/%m/%Y') + '.', '// Ne pas modifier à la main : relancer le script si la carte change.',
          '#pragma once', '']
lignes += [f'#define BROCHE_{nom:<14s} {g:>2d}' for nom, g in sorted(broches.items(), key=lambda x: x[1])]
open(SORTIE, 'w', encoding='utf-8').write('\n'.join(lignes) + '\n')
print('\n'.join(lignes))
