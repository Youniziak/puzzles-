# Chaîne « puzzle » — fiche pour une personne qui pourrait aider

Exylia Project — Kévin Chatellard
22 octobre 2026

## De quoi il s'agit

Je fais des cartes électroniques sans la vue. La chaîne « puzzle » transforme des blocs de circuit déjà routés en une carte prête pour l'usine (JLCPCB). Elle tient en une commande.

Elle ne refait pas ce que de bons logiciels font déjà. C'est un assemblage de logiciels maintenus chacun par leur équipe, reliés par un peu de colle en Python. Je cherche quelqu'un qui pourrait relire cette colle et m'aider à la maintenir.

## Les briques (ce n'est pas moi qui les maintiens)

| Brique | Rôle dans la chaîne | Version utilisée | Licence |
|---|---|---|---|
| EasyGerber (service en ligne) | route chaque bloc (10 à 30 composants) | carte du 22/10/2026 | service commercial |
| easyeda2kicad | télécharge les vraies empreintes et modèles 3D depuis la bibliothèque de JLCPCB | 1.0.1 | AGPL-3.0 |
| KiCad | assemble la carte, contrôle les règles (DRC), fait l'image 3D, échange avec Freerouting | 10.0.7 | GPL |
| Freerouting | trace les liaisons entre les blocs | 2.1.0 | GPL-3.0 |
| KiKit | produit les fichiers Gerber et perçages pour JLCPCB et PCBWay (avec la liste des pièces et le placement pour PCBWay) | 1.8.1 | MIT |
| gerbonara et shapely | relisent les fichiers Gerber pour un contrôle indépendant de KiCad | 1.6.3 et 2.2.0 | Apache-2.0 et BSD |
| CadQuery | fabrique la maquette à toucher (impression 3D) | 2.8.0 | Apache-2.0 |
| polars et le jeu « Open Schematics » (Hugging Face) | retrouvent comment d'autres projets publiés ont branché une puce (`outils/montages_reels.py`) | 2.0.0 ; jeu du 30/06/2026 | MIT ; CC-BY 4.0 |
| ngspice | simule l'électronique (à part, hors de la commande) | 42 | libre |

## La colle (ce qui est fait maison) — environ 4 800 lignes de Python

- `description.py` (150 lignes) : lit le fichier qui décrit la carte et les blocs. C'est le seul endroit qui sait ce qu'il y a sur la carte.
- `assembler.py` (215 lignes) : convertit les blocs EasyGerber en carte KiCad. Aucun outil ne fait cette conversion. Il vérifie chaque pastille contre EasyGerber, à 0,05 mm près.
- `freerouter.py` (111 lignes) : demande à KiCad ce qui manque, passe la main à Freerouting, reprend le résultat et fait le ménage. S'il manque encore une liaison, il relance Freerouting, jusqu'à 3 passages, avec des pistes d'alimentation plus fines.
- `fab.py` (55 lignes) : appelle KiKit, fusionne les listes de composants et de placement d'EasyGerber, fait l'image 3D.
- `verif_gerber.py` (293 lignes) : le contrôle indépendant. Il relit les fichiers envoyés à l'usine et cherche les coupures, les courts-circuits, les écarts trop petits, le cuivre interdit et les alimentations trop étroites.
- `maquette.py` (environ 490 lignes, avec `export_3mf.py`) : fabrique la maquette à toucher. La carte est agrandie trois fois, avec les vrais modèles 3D des composants, les pistes en relief, les sorties en plots, du braille et les noms en lettres. Elle sort en trois versions : un seul solide d'une couleur (STL) ; en couleurs, une couleur et une texture par bloc, en une pièce (3MF) ; ou en puzzle, une pièce par bloc à poser dans le fond (STL).
- `chaine.py` (environ 100 lignes) : enchaîne les étapes, de la relecture des scripts jusqu'au dossier de relecture (étape 7). Un contrôle qui trouve une erreur arrête tout ; une étape qui plante (erreur du programme) est signalée à la fin, avec le code de sortie 2.
- `relire_scripts.py` (environ 40 lignes) : relit les scripts de la chaîne avant de la lancer, en une seconde : erreurs de syntaxe, et noms inconnus avec pyflakes.
- `installer-ubuntu.sh` et `Dockerfile` : réinstallent tous les logiciels, dans les versions essayées. Essai du 23/10/2026 : l'image Docker se construit depuis une Ubuntu 24.04 neuve, et la chaîne y tourne de bout en bout, sans réseau, en 7 minutes. Ce qui reste à essayer : le script seul, sur une vraie machine Ubuntu.
- `schema.py` (275 lignes) : produit un schéma KiCad lisible, avec les vrais symboles, un cadre par bloc et une étiquette par liaison. KiCad le contrôle, et il est comparé à la carte broche par broche. Il est aussi exporté en PDF.
- `thermique.py` (59 lignes) : calcule l'échauffement des régulateurs et des amplis à partir des fiches des fabricants.
- `disponibilite.py` (85 lignes) : vérifie le stock et le prix de chaque pièce chez JLCPCB, juste avant de commander.
- `disposition.py` (75 lignes) : contrôle la disposition des blocs en moins d'une seconde, avant de router.
- `boitier.py` (environ 510 lignes) : fabrique un boîtier d'essai à imprimer, avec YAPP_Box (OpenSCAD, licence MIT) : ouvertures pour les prises, vrais boutons imprimés, noms en creux, plots qui tiennent la carte. Puis il contrôle le modèle : ouvertures traversantes, rien dans les parois, plots au contact, noms à leur place. Les ouvertures et boutons de chaque bloc sont déclarés dans son `bloc.json`.
- `banc_test.py` (environ 560 lignes) : fabrique un banc de test à pointes. Une petite carte du banc (dessinée dans KiCad, routée par Freerouting, préparée par KiKit) porte une pointe à ressort P75 sur chaque sortie de la carte et sur la couronne d'un trou de fixation relié à la masse ; chaque pointe mène à une borne. Trois pièces imprimées (CadQuery) : un socle avec des tétons dans les trous de fixation, un porte-pointes, et un capot où un entonnoir guide la pointe du multimètre sur chaque borne, avec le numéro en braille et en chiffres en relief. Il contrôle la carte du banc (KiCad), le trajet des pointes, les entonnoirs et le braille.
- `braille.py` (environ 30 lignes) : le braille par liblouis, la bibliothèque des lecteurs d'écran ; utilisé par la maquette, le banc et le plan sur papier gonflé.
- `controle_circuit.py` (environ 210 lignes) : avant de router, attrape les erreurs bêtes (masse ou alimentation mal branchée, SDA et SCL inversés, régulateur à l'envers, découplage trop loin, tirages I2C absents, trop de condensateurs sur le 5 V d'une prise USB, lignes USB sans résistance en série).
- `outils/typer_broches.py` (environ 140 lignes) et `sexpr.py` : donnent leur vrai type aux broches des symboles téléchargés, d'après la bibliothèque officielle de KiCad, pour que le contrôle électrique de KiCad voie quelque chose.
- `dossier_relecture.py` (environ 200 lignes) : réunit dans un zip tout ce qu'il faut à un électronicien pour relire une carte, avec un mot d'accompagnement et des PDF balisés (pandoc, LibreOffice). Il n'envoie rien.
- `plan_tactile.py` (environ 450 lignes) : un plan de la carte à imprimer sur papier gonflé, en quelques secondes, sans KiCad : contour, blocs, sorties, prises, trous, liaisons, avec du braille et une légende. Règles chiffrées dans `bibliotheque/regles/plan_tactile.json`.
- `broches_esp32.py` (environ 50 lignes) : écrit les broches de l'ESP32 pour le logiciel, à partir du schéma.
- `outils/mesures_guidees.py` (environ 140 lignes) : déroule les mesures du plan de test avec le banc ; valeur lue par sigrok ou tapée.
- `modeles3d.py` (environ 90 lignes) : pose les modèles 3D des composants comme sur la carte ; partagé par le boîtier et le banc.
- `fabricants.py` (140 lignes) : regarde si la carte convient aussi à d'autres fabricants (PCBWay, AISLER) que celui pour lequel elle est routée, avec KiCad et KiKit.

Aucun nom de carte, de bloc ou de réseau n'est écrit dans ces scripts. Une nouvelle carte, c'est un nouveau fichier de description, sans toucher au code.

## Ce qu'il faudra faire, et quand

- **KiCad 11** (pas encore sorti) retire l'ancienne interface Python (« SWIG »), que `assembler.py` et `freerouter.py` utilisent. Il faudra passer à la nouvelle (`kicad-python`, « IPC API »). C'est à partir de KiCad 11 qu'elle marche sans ouvrir la fenêtre de KiCad. D'ici là, la chaîne reste sur KiCad 10.
- **Freerouting** ignore la limite du nombre de passes en ligne de commande. Un routage prend donc environ 5 minutes.
- **EasyGerber** : son format d'export (`design.json`) n'est pas documenté publiquement. S'il change, `assembler.py` est à adapter.

## Ce que je cherche

Quelqu'un qui connaît Python et un peu KiCad, pour :
1. relire la colle (environ 4 800 lignes) et me dire ce qui est fragile ;
2. lancer la chaîne sur une vraie machine, avec Docker ou avec le script Ubuntu 24.04 ;
3. imprimer la maquette à toucher, de préférence en couleurs (240 × 247 mm pour la carte radio v4 ; en puzzle, les blocs tiennent sur un plateau de 22 × 22 cm, mais le fond demande un grand plateau). La notice `maquette-impression.txt` dit quelle pièce va dans quelle couleur ;
4. imprimer le plan sur papier gonflé (`resultats/radio-v4/plan-papier-gonfle/plan-tactile.pdf`, A4, à 100 %), si vous avez une machine à papier gonflé ; puis imprimer le boîtier d'essai (`boitier/`) et les trois pièces du banc de test (`banc-test/`), et souder les 20 pointes à ressort sur la carte du banc ; les notices `boitier.txt` et `banc-test.txt` disent comment ;
5. aider au passage à KiCad 11 le moment venu ;
6. relire une carte avant de la commander : pour la carte radio v4, les questions précises sont dans `cartes/radio-v4-questions-electronicien.md`.

Tout est dans le dossier : la méthode (`METHODE-CARTES-PUZZLE.md`), les scripts, la bibliothèque de blocs et trois cartes d'essai, avec leurs résultats.

## Ce qui a été essayé (22/10/2026)

- **Carte radio v3** (80 × 66 mm) : refaite avec la chaîne générique. 36 réseaux sur 36 complets, aucun court-circuit, rien sous l'antenne, alimentations assez larges.
- **Variante compacte** (66 × 75 mm) : les trois mêmes blocs, tous tournés, avec seulement un nouveau fichier de description. Mêmes résultats.
- **Prise USB-C** : ses deux trous de fixation étaient à 0,18 mm du cuivre de masse, alors qu'il faut 0,2 mm. Ce défaut venait du dessin du fabricant. Corrigé le 23/10/2026 en raccourcissant de 0,02 mm deux pastilles de masse : la carte radio passe maintenant tous les contrôles.
- **Schéma** : produit par la chaîne (`resultats/radio-v3/schema.pdf`, et `carte.kicad_sch` à ouvrir dans KiCad). Le contrôle électrique de KiCad ne trouve aucune erreur, et le schéma est identique à la carte.
- **Plan de test** à la réception : `cartes/radio-v3-plan-de-test.md`.
- **Stock (23/10/2026)** : sur la v3, 24 pièces sur 25 sont en stock chez JLCPCB ; **le tuner Si4735 manque.**
- **Autres fabricants (23/10/2026)** : la carte radio v4 convient aussi à PCBWay, après avoir agrandi 11 vias sur une copie ; pas à AISLER (Allemagne) telle quelle, dont les règles sont plus larges que celles d'EasyGerber. Le détail est dans `resultats/radio-v4/fabricants.txt`.
- **Carte radio v4** (80 × 66 mm) : la v3 avec un nouveau bloc tuner, autour du Si4732-A10, et une prise d'antenne à 0,53 $ au lieu de 10,65 $. Le bloc a été routé par EasyGerber et ajouté à la bibliothèque ; l'ancien reste. Tous les contrôles passent, et les 24 pièces sont en stock pour 5 cartes. Plan de test : `cartes/radio-v4-plan-de-test.md`.
- **Échauffement** : le régulateur 3,3 V (AMS1117) va pour la consommation habituelle de l'ESP32, pas au-delà d'environ 0,33 A. Le courant réel sera mesuré au test.
- **Placement** : ce n'est pas la chaîne qui place les blocs, c'est une personne (ou Claude). Une première disposition de la variante compacte tournait les sorties de l'ampli vers le bord de la carte. La chaîne s'est arrêtée et a dit quelle liaison manquait.
