"""Chaîne puzzle en une seule commande : des blocs routés par EasyGerber à la carte prête pour l'usine.
La carte est décrite par un fichier (cartes/ma-carte.json) ; les blocs viennent de la bibliothèque.
Aucun nom de carte ni de bloc n'est écrit dans les scripts.
  avant tout. relire_scripts.py — les scripts eux-mêmes : erreur de syntaxe, nom inconnu (pyflakes)     (une seconde)
  0. disposition.py — sorties tournées vers leurs partenaires, prises et antenne au bord              (quelques secondes)
  0 bis. thermique.py — échauffement des régulateurs et amplis, d'après les fiches des fabricants      (quelques secondes)
  0 quater. controle_circuit.py — erreurs « bêtes » : masse, alimentations, SDA/SCL, découplage, tirages I2C (quelques secondes)
  0 ter. plan_tactile.py — plan à toucher sur papier gonflé : la disposition des blocs, en PDF          (une dizaine de secondes)
  1. assembler.py  — vraies empreintes, pistes des blocs, plans, zones sans cuivre, règles du fabricant  (KiCad 10)
  2. freerouter.py — Freerouting trace ce qui manque, KiCad le reprend et contrôle                     (Freerouting, KiCad 10)
  3. fab.py        — Gerber, BOM et placement, image 3D, contrôle indépendant des Gerber                (KiKit, KiCad 10, gerbonara)
  3 bis. schema.py — schéma KiCad lisible (vrais symboles, une étiquette par liaison), ERC, PDF, schéma ↔ carte (KiCad 10)
  3 ter. disponibilite.py — stock chez JLCPCB, avec --disponibilite N (il faut internet)
  3 quater. fabricants.py — la carte convient-elle aussi à d'autres fabricants (PCBWay, AISLER…) ?    (KiCad 10, KiKit)
  4. maquette.py   — maquette à toucher, agrandie, à imprimer en 3D                                     (CadQuery)
  5. boitier.py    — boîtier d'essai à imprimer, avec ouvertures, boutons et noms en creux, contrôlé     (YAPP_Box, OpenSCAD)
  6. banc_test.py  — banc de test à pointes : petite carte du banc, socle, porte-pointes, capot en braille (KiCad, Freerouting, KiKit, CadQuery)
  7. dossier_relecture.py — tout ce qu'il faut envoyer à un électronicien, en un zip, avec un mot d'accompagnement (pandoc, LibreOffice)
Une étape qui plante (erreur du programme, pas un résultat de contrôle) est signalée à la fin, et ses fichiers sont dits
« pas à jour » : le 24/10/2026, l'étape 4 avait planté et la chaîne avait quand même écrit « Terminé ».
Code de sortie : 0 tout va bien ; 1 des points à corriger ; 2 une étape a planté.
Usage :
  python3 chaine.py cartes/ma-carte.json dossier_projet/ --freerouting chemin/freerouting.jar --kikit chemin/kikit \
      [--yapp chemin/YAPP_Box]"""
import argparse, os, subprocess, sys, time

p = argparse.ArgumentParser(description='Chaîne puzzle : assembler, router, fabriquer.')
p.add_argument('carte'); p.add_argument('projet')
p.add_argument('--freerouting', required=True); p.add_argument('--kikit', required=True)
p.add_argument('--sans-maquette', action='store_true', help='ne pas faire la maquette à toucher (étape 4, environ 11 minutes)')
p.add_argument('--yapp', help="dossier de YAPP_Box : fabrique le boîtier d'essai (étape 5, environ 3 minutes)")
p.add_argument('--sans-banc', action='store_true', help='ne pas faire le banc de test à pointes (étape 6, environ 3 minutes)')
p.add_argument('--disponibilite', type=int, metavar='N', help='vérifier le stock chez JLCPCB pour N cartes (il faut internet)')
a = p.parse_args()
ICI = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(a.projet, 'carte.kicad_pcb')

plantees = []       # étapes qui ont planté : leurs fichiers sont ceux d'avant

def etape(titre, script, *args):
    print(f'\n=== {titre} ===', flush=True)
    t = time.time()
    r = subprocess.run([sys.executable, os.path.join(ICI, script), *args], text=True, capture_output=True)
    sortie = [l for l in (r.stdout + r.stderr).splitlines() if not l.startswith(('./kicad', 'swig')) and 'assert' not in l and ': Debug: ' not in l]
    print('\n'.join(sortie[-40:]))
    if 'Traceback (most recent call last)' in r.stderr:
        plantees.append(titre)
        print("✗ CETTE ÉTAPE A PLANTÉ : c'est une erreur du programme, pas un résultat de contrôle. "
              "Ses fichiers sont ceux d'avant : pas à jour.")
    print(f'({time.time() - t:.0f} s)', flush=True)
    return r.returncode

def arret(message):
    """Arrêt de la chaîne ; si l'étape a planté, le dire, plutôt que d'annoncer un résultat de contrôle qui n'existe pas."""
    if plantees:
        sys.exit(f"Arrêt : l'étape « {plantees[-1]} » a planté (erreur du programme, voir ci-dessus).")
    sys.exit("Arrêt : " + message)

if etape('Avant tout : relire les scripts de la chaîne (syntaxe, noms inconnus)', 'relire_scripts.py'):
    arret("un script de la chaîne a une erreur (voir ci-dessus) : une étape planterait en route.")
if etape('0. Vérifier la disposition des blocs', 'disposition.py', a.carte):
    arret("la disposition des blocs est à revoir (voir ci-dessus), avant de perdre du temps à router.")
chaud = etape("0 bis. Échauffement des régulateurs et des amplis (d'après les fiches)", 'thermique.py', a.carte)
etape('0 ter. Plan à toucher sur papier gonflé (disposition des blocs)', 'plan_tactile.py', a.carte,
      os.path.join(a.projet, 'plan-papier-gonfle'))
if etape('0 quater. Contrôle du circuit : masse, alimentations, SDA/SCL, découplage, tirages I2C', 'controle_circuit.py', a.carte, a.projet):
    arret("le contrôle du circuit a trouvé une erreur (voir ci-dessus) : à corriger avant de router.")
if etape('1. Assembler les blocs', 'assembler.py', a.carte, a.projet):
    arret("l'assemblage signale un problème (voir ci-dessus).")
if etape('2. Router ce qui manque (Freerouting) et contrôler (KiCad 10)', 'freerouter.py', a.carte, PCB, a.freerouting):
    arret("des liaisons manquent après le routage (voir ci-dessus).")
code = etape("3. Fichiers pour l'usine, image 3D, contrôle indépendant", 'fab.py', a.carte, PCB, a.kikit)
if etape('3 bis. Schéma KiCad, contrôle électrique, comparaison schéma ↔ carte', 'schema.py', a.carte, PCB):
    code = code or 1
if a.disponibilite:
    if etape(f'3 ter. Stock des composants chez JLCPCB, pour {a.disponibilite} carte(s)', 'disponibilite.py', a.carte,
             str(a.disponibilite), os.path.join(a.projet, 'disponibilite.txt')):
        code = code or 1
etape("3 quater. Autres fabricants : la carte leur convient-elle aussi ?", 'fabricants.py', a.carte, PCB, a.kikit)
if not a.sans_maquette:
    etape('4. Maquette à toucher (impression 3D)', 'maquette.py', a.carte, PCB)
if a.yapp:
    if etape("5. Boîtier d'essai (impression 3D, YAPP_Box)", 'boitier.py', a.carte, PCB, a.yapp):
        code = code or 1
else:
    print("\n(étape 5, boîtier d'essai : sautée, il faut --yapp chemin/YAPP_Box)")
if not a.sans_banc:
    if etape('6. Banc de test à pointes (carte du banc et pièces à imprimer)', 'banc_test.py', a.carte, PCB, a.freerouting, a.kikit):
        code = code or 1
if etape("7. Dossier de relecture pour un électronicien (rien n'est envoyé)", 'dossier_relecture.py', a.carte, a.projet):
    print("(dossier de relecture incomplet : voir ci-dessus ; il manque souvent la fiche cartes/NOM-questions-electronicien.md)")
if plantees:
    print(f"\n✗ {len(plantees)} étape(s) ont planté (erreur du programme, pas un résultat de contrôle) : "
          + ' ; '.join(f"« {t} »" for t in plantees) + ". Leurs fichiers sont ceux d'avant : pas à jour, ne pas les utiliser.")
print('\nTerminé :', os.path.abspath(a.projet), '— MAIS AVEC DES ÉTAPES PLANTÉES (voir juste au-dessus)' if plantees else '',
      '' if code == 0 else '— avec des points à corriger (voir le bilan)',
      "— échauffement à surveiller (voir l'étape 0 bis)" if chaud else '')
sys.exit(2 if plantees else 1 if code else 0)
