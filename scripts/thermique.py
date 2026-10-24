"""Chaîne puzzle, étape 0 bis — bilan d'échauffement des composants qui chauffent (régulateurs, amplis).
Calcul simple, à partir des fiches des fabricants rangées dans bloc.json (« thermique ») :
  puissance perdue P, puis température de la puce = air ambiant + P × θJA (résistance thermique puce → air).
Deux cas : le cas maximal (courant prévu dans la description, ou pleine puissance) et le cas habituel (hypothèse écrite
dans bloc.json, à vérifier au test). Le cuivre autour du composant le refroidit mieux que ce que dit la fiche :
ce calcul est volontairement pessimiste.
Usage : python3 thermique.py cartes/ma-carte.json"""
import sys
from description import Carte

CARTE = Carte(sys.argv[1])
TH = CARTE.regles.get('thermique', {'temperature_ambiante_C': 40, 'marge_C': 10})
TA, MARGE = TH['temperature_ambiante_C'], TH['marge_C']
COURANTS = CARTE.courants

def verdict(p, tj, pmax, tjmax):
    if (pmax and p > pmax) or tj > tjmax:
        return '✗ trop chaud'
    if tj > tjmax - MARGE:
        return '⚠ juste'
    return '✓'

trop, juste, lignes = [], [], []
for b in CARTE.blocs:
    for t in b.bloc.get('thermique', []):
        ref = CARTE.repere(b, t['composant'])
        cas = []
        if t['type'] == 'regulateur_lineaire':
            chute = t['tension_entree_V'] - t['tension_sortie_V']
            i_max = COURANTS.get(CARTE.reseau(b, t['reseau_sortie']))
            if i_max:
                cas.append((f"courant prévu {i_max} A", chute * i_max))
            cas.append((f"courant habituel {t['courant_typique_A']} A (hypothèse)", chute * t['courant_typique_A']))
        elif t['type'] == 'ampli_classe_d':
            p_out = t['canaux'] * t['puissance_sortie_max_W']
            perte = p_out * (1 / t['rendement'] - 1)
            cas.append((f"pleine puissance en continu, {t['canaux']} × {t['puissance_sortie_max_W']} W sur {t['charge']}", perte))
            cas.append((f"musique, environ {t['part_moyenne_musique']:.0%} de la pleine puissance (hypothèse)", perte * t['part_moyenne_musique']))
        lignes.append(f"{ref} — {t['nom']} (bloc {b.id})")
        for libelle, p in cas:
            tj = TA + p * t['theta_ja_C_par_W']
            v = verdict(p, tj, t.get('puissance_max_W'), t['tj_max_C'])
            lignes.append(f"   {v:13s} {libelle} : {p:.2f} W perdus → puce vers {tj:.0f} °C (limite {t['tj_max_C']} °C"
                          + (f", {t['puissance_max_W']} W au plus" if t.get('puissance_max_W') else '') + ')')
            if v.startswith('✗'):
                trop.append(f"{ref} ({t['nom']}) : {libelle}")
            elif v.startswith('⚠'):
                juste.append(f"{ref} ({t['nom']}) : {libelle}")
        lignes.append(f"   source : {t['source']}")
print(f"== Échauffement (air autour de la carte : {TA} °C) ==")
print('\n'.join(lignes) if lignes else '  aucun composant à surveiller dans ces blocs')
print('== Bilan thermique ==')
for x in trop:
    print('  ✗', x)
for x in juste:
    print('  ⚠', x)
if not trop and not juste:
    print('  ✓ rien ne chauffe trop')
sys.exit(1 if trop else 0)
