# Chaîne « puzzle » pour faire une carte électronique sans la vue

Exylia Project — méthode de la chaîne SKiDL
Version 1.28 — 24 octobre 2026

## L'idée en une phrase

On découpe la carte en blocs par fonction. Chaque outil fait la partie où il est bon, et deux contrôles indépendants vérifient tout à la fin.

## Des briques, pas un programme en dur

La chaîne est un assemblage de logiciels maintenus chacun par leur équipe : EasyGerber, easyeda2kicad, KiCad, Freerouting, KiKit, gerbonara, CadQuery, OpenSCAD, YAPP_Box, liblouis (braille), PlatformIO, sigrok, pandoc, LibreOffice et pyflakes. Entre eux, de la colle en Python (environ 4 800 lignes), qui ne connaît aucune carte.

Ce qui change d'une carte à l'autre est rangé dans des fichiers, pas dans le code :
- **la bibliothèque de blocs** (`bibliotheque/blocs/`) : un dossier par bloc validé, avec son export EasyGerber et un fichier `bloc.json`. Ce fichier donne :
  - les réseaux qui sortent du bloc ;
  - les pastilles de sortie (à ne pas poser) ;
  - les zones sans cuivre, comme l'antenne ;
  - les courants demandés.
- **les règles du fabricant** (`bibliotheque/regles/`) : écarts, perçages, marge sur la largeur des alimentations.
- **la carte** (`cartes/`) : son contour, et la liste des blocs posés, chacun avec sa position et sa rotation (0, 90, 180 ou 270 degrés).

Un bloc garde ses règles où qu'on le pose : tourner le bloc tourne aussi sa zone d'antenne. La fiche `POUR-LE-FABLAB.md` décrit les briques et la colle pour quelqu'un qui voudrait aider.

## Les étapes

0. **Regarder comment d'autres ont fait** (`outils/montages_reels.py`, hors de la commande, quelques minutes avec internet). Pour une puce, le script cherche dans le jeu de données libre « Open Schematics » (Hugging Face, environ 88 000 schémas KiCad publiés) les projets qui l'utilisent, et écrit ce qui est branché sur chacune de ses broches. Ce sont des montages publiés, pas vérifiés : ils servent à comparer et à poser de bonnes questions. Essai du 23/10/2026 : deux projets avec un Si4732-A10 ont exactement notre montage du tuner ; plusieurs mettent 10 kΩ en série devant l'ampli.

   Chercher aussi sur hackaday.io (avec Firecrawl, recherche « site:hackaday.io » et le nom de la puce). C'est une source de premier rang : des professionnels et des amateurs reconnus y publient des projets aboutis, avec schémas, plans et récits d'essais, problèmes compris.

   **Croiser les sources.** Une piste est retenue quand au moins deux sources indépendantes la donnent : hackaday.io, Open Schematics, hackaday.com, le forum KiCad, EEVblog, GitHub, Instructables. Exemple : le quartz de 32,768 kHz avec deux 22 pF et 100 nF sur VDD du tuner se retrouve dans 4 projets de 3 auteurs différents (deux versions de ralphxavier/SI4735, pico-radio-5, Fennec) ; c'est un bon signe. Là où les projets diffèrent, c'est une question pour l'électronicien. Seul l'essai sur prototype prouve qu'un montage marche.

   Y chercher aussi **ce que la chaîne ne sait pas encore faire** : voir « Pistes trouvées sur hackaday.io », plus bas. Essai du 23/10/2026 : la radio Fennec (CiferTech, licence MIT) a la même architecture que la radio v4, ESP32-S3, Si4732-A10 et PAM8403, et la même prise du son du tuner vers l'entrée IO1 de l'ESP32. Ses choix sont repris dans la fiche de questions (version 1.2) et le plan de test (version 2.1).

   Sur hackaday.io, la même recherche n'a trouvé aucun projet de conception de cartes sans la vue, ni de maquette de carte à toucher : surtout des aides pour les personnes aveugles (afficheurs braille, guidage par vibrations). Ça ne prouve pas que rien n'existe ailleurs.
1. **Décrire le circuit en texte.** C'est la liste des composants et de leurs liaisons. Fichier `intent.json`, écrit avec `carte_radio.py`.
2. **Placer les composants.** Claude le fait, avec les règles d'électronique :
   - condensateurs de découplage à moins de 5 mm ;
   - quartz près de la puce ;
   - antenne et prises au bord.
3. **Découper en blocs**, par exemple alimentation et microcontrôleur, tuner, ampli.
   - Chaque signal qui passe d'un bloc à un autre reçoit une **sortie** au bord du bloc. C'est une pastille de test de 2,8 × 1,5 mm, qui sert aussi à mesurer au multimètre.
   - Les sorties sont rangées dans le même ordre que les broches, pour que les fils ne se croisent pas.
   - Script : `preparer_v3.py`.
4. **Router chaque bloc** dans EasyGerber. Il est rapide et propre sur un petit bloc.

   Un bloc validé va dans la bibliothèque, et la carte suivante peut le réutiliser sans le refaire.

   Un bloc validé ne se modifie pas. S'il faut changer une pièce, on fait un nouveau bloc sous un autre nom, et l'ancien reste. Exemple du 23/10/2026 : `B_tuner_si4732` remplace `B_tuner` sur la carte radio v4, et la v3 garde l'ancien. Avant de router, on lit sur l'empreinte KiCad (sérigraphie) dans quel sens sort chaque prise : le modèle 3D a l'axe y inversé, il trompe.

Les étapes 5 à 8 se font en une seule commande, `chaine.py` (dossier `scripts/`, avec KiCad 10) :

```
python3 scripts/chaine.py cartes/radio-v3.json resultats/radio-v3 --freerouting chemin/freerouting.jar --kikit chemin/kikit
```

Durée constatée : de 6 à 11 minutes, selon que Freerouting a besoin d'un deuxième passage ; une vingtaine de minutes avec la maquette, le boîtier et le banc.
- Avant tout, la commande relit ses propres scripts, en une seconde (`relire_scripts.py`) : une erreur de syntaxe ou un nom inconnu (pyflakes) l'arrête avant de commencer.
- Si un contrôle trouve une erreur, la commande s'arrête et dit pourquoi.
- Si une étape plante (erreur du programme, pas un résultat de contrôle), la commande le dit à la fin, en majuscules, et ses fichiers sont dits « pas à jour ». Code de sortie : 0 tout va bien, 1 des points à corriger, 2 une étape a planté.

Deux cartes faites avec la même bibliothèque, sans toucher au code (22/10/2026) :
- `cartes/radio-v3.json` : la carte radio v3, 80 × 66 mm ;
- `cartes/radio-compacte.json` : les trois mêmes blocs, tous tournés de 270°, 66 × 75 mm.

Le 23/10/2026, après correction de la prise USB-C, la carte radio v3 passe tous les contrôles. Le bilan du contrôle indépendant dit « rien à corriger », et KiCad ne trouve aucune erreur.

   Avant tout, la commande **contrôle la disposition** (`disposition.py`), en moins d'une seconde et sans KiCad. Elle s'arrête si :
   - une sortie de bloc est tournée vers le bord de la carte ;
   - une prise ou l'antenne n'est pas au bord (« au_bord » dans `bloc.json`).

   Elle avertit si une liaison devra faire le tour d'un bloc. Essai du 23/10/2026 : elle refuse la première disposition de la variante compacte (`cartes/essai-disposition-refusee.json`), en désignant le 5 V de l'ampli, celui que Freerouting n'avait pas pu relier après 15 minutes.

   Puis elle fait le **contrôle du circuit** (`controle_circuit.py`, étape 0 quater, quelques secondes, sans KiCad). Il lit le nom, le type et la liaison de chaque broche, et sa position :
   - **Il arrête la commande (✗)** sur :
     - une broche de masse hors de la masse ;
     - une alimentation branchée sur la masse ;
     - SDA et SCL inversés ;
     - un régulateur à l'envers (tension lue dans le nom des liaisons).
   - **Il signale (⚠)** :
     - gauche et droite inversées ;
     - une broche NC reliée ;
     - une entrée en l'air ;
     - une alimentation de puce sans condensateur vers la masse à moins de 5 mm ;
     - un bus I2C sans résistance de tirage ;
     - plus de 10 µF de condensateurs sur le VBUS d'une prise USB (règle de l'USB 2.0, pour la charge prise au branchement) ;
     - une ligne de données USB qui va de la prise à une puce sans résistance en série (Espressif recommande d'en prévoir la place sur l'ESP32-S3).
   - Ces deux dernières règles viennent des contrôles de kicad-happy, refaits à la main le 24/10/2026. Essai : sur une copie de la radio v4 où les deux défauts sont corrigés (4,7 µF au lieu de 22, 1 µF au lieu de 10, une résistance de 22 Ω sur D+), les alertes correspondantes disparaissent ; seule reste celle de D-, qu'on n'avait pas touchée.
   - Une alerte vérifiée par une personne (erreur du catalogue, choix voulu) se note dans `bibliotheque/controles-verifies.json`, avec la raison, qui et quand. Elle n'est plus comptée, mais reste écrite.
   - Premier cas, le 24/10/2026 : le quartz du tuner a deux broches, et le catalogue nomme « GND » l'une d'elles. Ce n'est pas une erreur de la carte.
   - Sur la radio v4 : aucune erreur. Tous les découplages sont à moins de 5 mm, les deux tirages I2C sont là, le régulateur est dans le bon sens. Trois points à regarder depuis le 24/10/2026 : 33 µF sur VBUS, et les deux lignes USB sans résistance en série (questions 11 et 12 de la fiche). Sur l'ancien tuner Si4735 (v3), trois points de plus : l'entrée DFS en l'air, et deux broches NC reliées à la masse.
   - Ce qu'il ne voit pas : la tension que supporte chaque broche (il faudrait les fiches), ni si une valeur est bonne.

   Puis elle fait le **plan à toucher sur papier gonflé** (`plan_tactile.py`, environ 10 secondes, sans KiCad), dans `plan-papier-gonfle/`. On peut aussi le lancer seul dès que la disposition est écrite : `python3 scripts/plan_tactile.py cartes/NOM.json dossier/`. Il sert à sentir la disposition des blocs en quelques minutes, sans attendre une impression 3D. C'est un PDF A4 à l'italienne, à imprimer à 100 % sur papier gonflé (PIAF, Zychem…) :
   - **Page 1, la carte** :
     - le contour en trait épais ;
     - les blocs en tirets, avec leur nom en braille ;
     - les sorties en petits carrés pleins ;
     - les prises et les fils en pavés pleins ;
     - les trous de fixation en anneaux ;
     - les zones sans cuivre en hachures.
   - **Page 2, les liaisons** : un trait droit d'une sortie à sa partenaire, comme le « chevelu » de KiCad. Ce n'est pas le chemin de la vraie piste.
   - **Sur ces deux pages, une colonne à gauche** : le titre en braille, puis la clé, c'est-à-dire chaque symbole suivi de son nom en un mot de braille.
   - **Pages suivantes, la légende en braille** : les sorties dans l'ordre de lecture, avec leur numéro du plan de test ; les prises ; les trous ; les zones.
   - **La notice** (`plan-tactile.txt`) donne la même légende en texte, pour le lecteur d'écran, avec la liste des liaisons et les contrôles :
     - au moins 3 mm entre deux objets ;
     - au moins 6 mm d'une sortie à sa voisine, de centre à centre ;
     - le nom des blocs à 6 mm de tout ;
     - les liaisons qui se croisent.
   - **Règles chiffrées** : `bibliotheque/regles/plan_tactile.json`. Elles viennent de Monica Houston (Hackster, 2023) : trait de 1,3 mm au plus, 6 mm de vide autour des objets, braille à 6 mm de son objet. Le texte pour les personnes qui voient est en bleu, et ne gonfle pas.
   - **Essai du 23/10/2026 sur la radio v4** : agrandie 2,5 fois, 4 pages. Tous les objets sont à plus de 3 mm, et toutes les sorties à 6 mm au moins.
     - Le plan montre deux croisements de liaisons. Le son gauche et le son droit sont rangés dans l'ordre inverse sur le tuner et sur l'ampli : au routage, l'un passe sur l'autre face. Le 3,3 V et le son gauche se croisent aussi.
     - Le trait du son gauche passe à 1,2 mm de la sortie 15.
     - Rien n'est encore imprimé : les épaisseurs sont à ajuster après le premier essai.

5. **Recoller les blocs** dans KiCad (`assembler.py`). Le script :
   - pose les vraies empreintes des composants, avec leur dessin et leur modèle 3D. Elles sont téléchargées par easyeda2kicad (libre) depuis la bibliothèque de JLCPCB. Chaque pastille doit coïncider avec celle d'EasyGerber à 0,05 mm près, sinon le script s'arrête ;
   - met chaque bloc à sa place et dans son sens, et vérifie qu'aucun bloc ne déborde ni n'en chevauche un autre ;
   - ajoute les plans de masse et les zones sans cuivre des blocs ;
   - pose les trous de fixation, si la carte en décrit (« trous_fixation ») : trous M3 métallisés, reliés à la masse par les plans. En « auto », la chaîne les place là où il n'y a ni bloc, ni zone sans cuivre, ni couloir entre deux blocs (les liaisons y passent), au plus près des coins. Ils sont « sur la carte seulement » : hors schéma, liste des pièces et placement ;
   - écarte toute piste de bloc fautive : trop près d'un autre réseau, ou trop étroite pour son courant ;
   - écrit dans le projet les règles du fabricant et une classe par alimentation, avec la largeur que demande son courant.
6. **Router ce qui manque** avec Freerouting (`freerouter.py`).
   - KiCad dit quels réseaux sont incomplets.
   - KiCad transmet lui-même à Freerouting la largeur de chaque alimentation.
   - Un plan d'alimentation coupé en îlots est laissé de côté : Freerouting relie ses broches par de vraies pistes.
   - KiCad 10 reprend lui-même le résultat de Freerouting. Le script ne garde que le cuivre ajouté sur les réseaux incomplets, puis enlève les bouts de piste qui ne mènent nulle part.
   - Les alimentations reçoivent d'abord une largeur confortable : 1,5 fois le minimum que demande leur courant. S'il manque encore une liaison, un deuxième passage repart du premier, avec la largeur minimale pour les alimentations encore incomplètes. Constaté le 22/10 : à 2 fois le minimum (1,1 mm pour le 5 V), Freerouting n'arrivait pas à relier le 5 V.
7. **Produire les fichiers pour JLCPCB** (`fab.py`) :
   - Gerber et perçages par KiKit (libre) ;
   - liste des composants (BOM) et placement, repris d'EasyGerber bloc par bloc. Les pastilles de sortie sont du cuivre nu : il n'y a rien à poser dessus ;
   - une image 3D de la carte.
8. **Vérifier deux fois** :
   - le contrôle de KiCad ;
   - le contrôle électrique du schéma (ERC), avec de **vrais types de broches** (depuis le 24/10/2026) :
     - Les symboles d'easyeda2kicad n'en ont presque pas : 75 broches sur 81 sont « non définies » dans les données LCSC des pièces de la radio, et parfois fausses.
     - `outils/typer_broches.py` reprend les types de la bibliothèque officielle de KiCad (règles KLC), broche par broche, pour les pièces listées dans `bibliotheque/empreintes/symboles-officiels.json`. Pour la radio : l'ESP32-S3, l'AMS1117, l'USBLC6, le PAM8403, la prise USB-C et les Si4735/Si4732. Le Si4732-A10 est absent de cette bibliothèque : ses types sont repris du Si4735, de la même famille, en rapprochant les noms.
     - Les pièces passives (résistances, condensateurs, quartz, LED, boutons, prises, pastilles) reçoivent « passive ». Les numéros de broches restent ceux de LCSC : rien ne peut se décaler.
     - Le résultat (`types-broches.json`) se relit. Le script liste aussi les noms qui diffèrent entre LCSC et KiCad (VOUT et VO, OUTL+ et LOUT+…) : c'est là qu'une numérotation décalée se verrait.
     - `schema.py` applique ces types. Il pose un drapeau d'alimentation (PWR_FLAG) sur la masse et sur les liaisons de « alimentations_externes » de la carte (le VBUS de la prise USB). Il utilise des étiquettes globales, pour que les liaisons portent le même nom que sur la carte.
     - Essai du 24/10/2026, en cassant exprès trois copies de la radio v4 :
       - drapeau du VBUS retiré : erreur « alimentation non fournie » ;
       - broche NC du PAM8403 reliée au 5 V : avertissement ;
       - deux sorties de l'ampli reliées : erreur « sortie contre sortie ».
       Avant, avec les broches « non définies », aucune des trois ne ressortait. La vraie carte : aucune erreur, aucun avertissement.
   - la **parité schéma ↔ carte de KiCad** (`kicad-cli pcb drc --schematic-parity`), lancée par `schema.py` : liaisons et champs de chaque composant. Constaté le 24/10/2026 : sur la carte, 18 condensateurs et résistances portaient la référence LCSC d'une autre pièce, celle qui avait servi à télécharger leur empreinte 0603, partagée. Les fichiers envoyés à l'usine étaient justes, car ils viennent d'EasyGerber, mais le fichier KiCad, lui, était faux. `assembler.py` écrit maintenant sur chaque empreinte la référence LCSC, le MPN, le fabricant et la fiche de la vraie pièce ;
   - `verif_gerber.py`, qui relit les fichiers envoyés à l'usine sans passer par KiCad. Il vérifie :
     - les coupures et les courts-circuits ;
     - les écarts entre pistes ;
     - les zones sans cuivre des blocs et le bord de la carte ;
     - les perçages, les trous et les couronnes ;
     - la largeur du cuivre de chaque alimentation par rapport à son courant.
   Les deux contrôles sont lancés par la commande. Le second est écrit dans `controle-independant.txt`. Il finit par un bilan : la liste de ce qui est à corriger avant de commander, avec les seuils du fabricant.
9. **Simuler l'électronique** avec ngspice (libre), là où le dessin ne dit rien : niveaux de tension, fréquences de coupure, charge que voit une sortie (dossier `simulation/`).
9 bis. **Faire le schéma** (`schema.py`), pour la relecture par des humains, au FabLab par exemple. Le schéma est tiré de la carte assemblée :
    - un cadre par bloc ;
    - les vrais symboles des composants, téléchargés par easyeda2kicad (`bibliotheque/empreintes/radioneo.kicad_sym`) ;
    - sur chaque broche, un petit fil et une étiquette au nom de la liaison ;
    - une croix sur les broches libres.

    KiCad le contrôle (contrôle électrique, ou ERC) et l'exporte en PDF (`schema.pdf`). Puis la liste des liaisons du schéma est comparée à la carte, broche par broche. Essai du 23/10/2026 : aucune erreur, et le schéma est identique à la carte. Les symboles téléchargés avaient deux défauts, corrigés dans la bibliothèque :
    - les résistances, les condensateurs et le quartz déclaraient leurs broches comme des « entrées » au lieu de « passives » ;
    - une broche du quartz s'appelait « GND » alors qu'elle n'est pas à la masse.

9 ter. **Vérifier l'échauffement** (`thermique.py`, étape 0 bis de la commande, quelques secondes). Pour chaque régulateur et chaque ampli décrit dans `bloc.json` (« thermique »), le script calcule la puissance perdue, puis la température de la puce, à partir des chiffres des fiches des fabricants. Il le fait dans deux cas : le cas maximal, et le cas habituel. Le cas habituel est une hypothèse écrite noir sur blanc, à vérifier au test. Air autour de la carte : 40 °C. Constat du 23/10/2026 sur la carte radio :
    - le régulateur AMS1117 supporte la consommation habituelle (0,25 A : environ 104 °C, limite 125 °C), mais pas les 0,8 A prévus dans la description ;
    - l'ampli PAM8403 se protège tout seul à pleine puissance continue sur 4 Ω.

9 quater. **Vérifier la disponibilité des composants** (`disponibilite.py`, option `--disponibilite N` de la commande, avec internet), juste avant de commander. Pour chaque pièce, le script donne :
    - le stock chez JLCPCB, et s'il couvre N cartes ;
    - le type de pièce : « de base », ou « étendue », avec des frais de chargement ;
    - le prix.

    La source est la recherche de pièces de JLCPCB (une interface non documentée), avec LCSC en secours. Constat du 23/10/2026 :
    - le tuner Si4735 est à 0 en stock chez JLCPCB, et l'une de ses versions est marquée « abandonnée ». JLCPCB ne peut pas assembler la carte radio telle quelle ;
    - le connecteur d'antenne coûte 10,65 $ pièce. Des modèles équivalents existent à environ 0,53 $.

    Réponse, carte radio v4 : nouveau bloc tuner avec le Si4732-A10 (155 en stock, 2,88 $) et la prise BWSMA-KWE-Z001 (127 516 en stock, 0,53 $). Les 24 pièces sont en stock pour 5 cartes ; composants pour 5 cartes : environ 54 $, hors carte, pose et port.

9 quinquies. **Regarder les autres fabricants** (`fabricants.py`, étape 3 quater de la commande, environ 15 secondes). La carte est routée pour le fabricant de sa description, mais on peut vouloir la faire faire ailleurs. Chaque fichier de règles de `bibliotheque/regles/` marqué « fabricant » est essayé :
    - KiCad contrôle une copie de la carte avec les règles de ce fabricant, plans de cuivre refaits ;
    - KiCad en sort les fichiers Gerber, et le contrôle indépendant les relit avec les mêmes règles ;
    - si tout passe et que KiKit connaît ce fabricant, KiKit prépare ses fichiers, liste des pièces et placement compris ;
    - le résumé est dans `fabricants.txt`. Les règles viennent des pages des fabricants, avec la date et l'adresse dans chaque fichier ; ce qu'ils ne publient pas est écrit comme tel.

    Fabricants décrits le 23/10/2026 :
    - **JLCPCB** : celui des cartes radio ; stock des pièces vérifiable (étape 3 ter).
    - **PCBWay** : la carte radio v4 passe, à une retouche près, faite sur la copie seulement : 11 vias du bloc tuner ont une couronne de 0,1375 mm, et PCBWay demande 0,15 mm ; ils sont agrandis à 0,55 mm, puis tout est recontrôlé. Fichiers préparés par KiKit. Le stock des pièces ne se vérifie pas d'ici : PCBWay les achète lui-même.
    - **AISLER** (Allemagne, pour un fabricant européen) : la carte ne passe pas telle quelle. Leur procédé le plus fin demande 0,125 mm d'écart, des trous d'au moins 0,25 mm, une couronne de 0,3 mm autour des broches. Or les blocs d'EasyGerber sont routés à 0,1 mm avec des vias de 0,2 mm, et l'empreinte du fabricant de la prise USB-C est trop serrée. Il faudrait des blocs routés plus large et une autre prise USB-C.
    - **Eurocircuits** (Belgique) : pas ajouté. Sa table de classes n'est publiée qu'en image, que je n'ai pas pu lire ; à leur demander.
    - **Proto-Electronics** (usines à Rosheim, en France, et à Braga, au Portugal ; circuit et assemblage) : pas encore ajouté. Leurs règles de fabrication ne sont pas publiées sur leur site (vérifié le 23/10/2026) ; à leur demander, puis écrire `proto-electronics-2-couches.json`.

10. **Faire la maquette à toucher** (`maquette.py`, avec CadQuery). C'est la dernière étape de la commande, qu'on peut sauter avec `--sans-maquette`. La carte est agrandie trois fois, en un seul solide à imprimer en 3D (`maquette-a-toucher.stl`, environ 14 Mo ; en STEP sur demande, environ 90 Mo). Elle sert à montrer au FabLab à quoi ressemble la carte, et à la vérifier du bout des doigts :
    - les composants sont leurs vrais modèles 3D, agrandis ;
    - les pistes du dessus sont en relief, celles du dessous en creux sous la plaque (il faut retourner la maquette) ;
    - les sorties des blocs sont des plots, plus hauts que les pistes ;
    - une rainure sépare les blocs. Le nom de chaque bloc est en braille dans le bloc ; s'il n'y a pas la place, c'est une lettre, expliquée dans la légende ;
    - la légende en braille, sous la carte, donne le nom et l'échelle. Un coin coupé, en haut à gauche, indique le sens.

    Les réglages sont dans `bibliotheque/regles/maquette.json`. La carte radio v4 donne 240 × 247 mm, donc il faut un plateau d'au moins 25 × 25 cm, ou baisser l'échelle. Le connecteur d'antenne et la prise USB-C demandent des supports à l'impression.

    Depuis la version 1.10, la maquette existe aussi en couleurs, pour qu'une personne qui n'est pas du métier comprenne tout de suite :
    - chaque bloc a sa couleur (palette d'Okabe et Ito, lisible aussi par les personnes qui distinguent mal les couleurs) et sa texture en creux : lignes, quadrillage, trous. La couleur et la texture disent la même chose, l'une aux yeux, l'autre aux doigts : c'est la règle du RGAA, jamais une information par la couleur seule ;
    - le nom de chaque bloc est écrit en grosses lettres en relief, à côté du braille, ainsi que le nom de la carte et l'échelle ;
    - tout ce qui dépasse de la plaque (pistes, composants, braille, lettres) est noir ;
    - `maquette-couleurs.3mf` : en une pièce, pour une imprimante à plusieurs bobines ;
    - `maquette-puzzle/` : une pièce par bloc, plus le fond, chacune dans sa couleur, pour une imprimante à une bobine. Un bloc se pose dans son logement du fond, sur une pente à 45° ; il peut s'enlever, comme un bloc qu'on change dans la chaîne (l'ancien tuner contre le nouveau), ou se coller ;
    - `maquette-impression.txt` dit à la personne qui imprime quelle pièce va dans quelle couleur, et où faire la pause pour passer au fil noir.

    Sur la carte radio v4, les blocs tiennent sur un plateau de 22 × 22 cm, mais pas le fond (240 × 247 mm depuis l'ajout des trous de fixation). L'étape prend environ 11 minutes au lieu de 3. Ce qui n'est pas encore essayé : l'impression elle-même, et l'ouverture du 3MF dans un logiciel d'impression (le fichier a été relu par un autre programme, trimesh).

11. **Faire le boîtier d'essai** (`boitier.py`, avec YAPP_Box et OpenSCAD). Étape 5 de la commande, avec `--yapp chemin/YAPP_Box`, environ 3 minutes. Le script ne dessine rien lui-même : il lit la carte et les modèles 3D, et écrit les réglages de YAPP_Box (licence MIT, maintenu) :
    - la taille vient de la carte, des pattes qui dépassent dessous et du plus haut composant ;
    - chaque bloc déclare, dans son `bloc.json` (« boitier »), ses prises à ouvrir dans la paroi, ses boutons et lumières à sortir sur le dessus, et ses prises à fils. Une ouverture prend la taille de la bouche de la prise, mesurée sur son modèle 3D, ou de la fiche qu'on y branche si elle est plus grande (surmoulage d'une fiche USB-C, écrou d'une antenne SMA) ;
    - les boutons sont de vrais boutons imprimés, ronds ou carrés pour les reconnaître au toucher ; le nom de chaque prise, passage de fils et bouton est écrit en creux dans le dessus, à côté ;
    - la carte est tenue par ses trous de fixation, ou, si elle n'en a pas, pincée entre des plots du fond et du dessus, là où il n'y a ni composant ni patte ;
    - le dessus se ferme par deux crochets, placés sur des parois sans ouverture.

    Puis le script contrôle le modèle : le dessus est remis en place par le calcul, les ouvertures et les trous doivent traverser, aucun composant ni la carte ne doit rentrer dans une paroi, les plots doivent toucher la carte, et les noms doivent être creusés à leur place sans déborder sur un voisin. Ce dernier contrôle regarde le dessus vu d'en haut, comme une image des hauteurs (`boitier-dessus-vu-de-dessus.png`). Réglages : `bibliotheque/regles/boitier.json`. La notice pour la personne qui imprime est `boitier.txt`.

    Radio v4, le 23/10/2026, avec ses trous de fixation : fond de 86 × 79 × 10 mm et dessus de 86 × 79 × 16 mm, tous les contrôles passent. La carte est tenue par un téton dans chacun de ses 4 trous, et pincée par 2 plots aux coins du bas, qui n'ont pas de trou. Les lettres sont creusées (le dessus s'imprime face contre le plateau) : du braille en relief n'y est pas possible. Rien n'est encore imprimé.

12. **Faire le banc de test à pointes** (`banc_test.py`). Étape 6 de la commande, environ 3 minutes ; `--sans-banc` la saute. Il sert à mesurer toutes les sorties sans viser une pastille de 1,5 mm avec la pointe du multimètre :
    - la carte se pose dans un **socle** imprimé, sur des tétons qui entrent dans ses trous de fixation, et sur des appuis sous les sorties ;
    - au-dessus, une **carte du banc** (dessinée dans KiCad, routée par Freerouting, contrôlée par KiCad, préparée pour JLCPCB par KiKit) porte une pointe à ressort P75 sur chaque sortie, et une sur la couronne d'un trou de fixation relié à la masse. Ses pistes mènent chaque pointe à une borne ronde ;
    - un **porte-pointes** imprimé guide les pointes ; un **capot** imprimé couvre la carte du banc : au-dessus de chaque borne, un entonnoir guide la pointe du multimètre jusqu'à la borne, avec le numéro de la sortie en braille (notation Antoine, réglable) et en chiffres en relief. La masse a un entonnoir carré, pour la reconnaître au toucher. Les bornes sont rangées comme on lit : en rangées alignées, de gauche à droite et de haut en bas ; un coin coupé en haut à gauche donne le sens ;
    - quatre vis M3 et quatre écrous papillon serrent le tout à la main ; des colonnes fixent la hauteur, donc l'enfoncement des pointes (1,7 mm sur 2,65 possibles) ;
    - les côtés restent libres devant les prises et les passages de fils : on peut brancher l'USB pendant les mesures.

    Le script contrôle : la carte du banc (KiCad sans erreur, chaque borne reliée à sa pointe), le trajet de chaque pointe (aucun composant frôlé), les pièces fermées, la carte posée sans autre contact que ses appuis, les entonnoirs ouverts jusqu'à leur borne et loin des pointes, et le braille complet (chaque point à sa place et séparé de ses voisins), sur une image du capot vu d'en haut (`banc-capot-vu-de-dessus.png`). Réglages : `bibliotheque/regles/banc_test.json`. Notice : `banc-test/banc-test.txt`.

    Sous chaque entonnoir : le numéro de la sortie en gros chiffres en relief, et le nom du signal en lettres en relief (5V, SDA, MUTE, SON G… : « noms_courts » dans la description de la carte, sinon la fin du nom de la liaison). Le braille vient en plus (liblouis, table française) et se désactive dans `banc_test.json` (« braille » à false) : la carte du banc est alors plus petite.

    Radio v4, le 23/10/2026 : avec le braille, carte du banc de 130 × 123 mm ; sans le braille, 110 × 103 mm. 20 bornes (masse, puis 1 à 19), 13 contrôles sur 13. Il faut acheter 20 pointes P75, 4 vis M3 × 30 mm à tête hexagonale et 4 écrous papillon M3 ; la carte du banc se commande sans composant, les pointes se soudent à la main. Les cotes des pointes viennent de fiches de vendeurs, qui ne sont pas toutes d'accord : les mesurer à la réception. Rien n'est encore fabriqué.

13. **Faire tourner la carte : programme d'essai et mesures guidées.**
    - `scripts/broches_esp32.py` lit dans la liste des liaisons (schema.net) les broches de l'ESP32 et écrit `broches.h` : le logiciel ne recopie aucune broche à la main.
    - Le programme d'essai de la carte (radio v4 : `cartes/radio-v4-essai/`, PlatformIO, versions figées) suit l'étape 6 du plan de test : LED, molette, bus I2C avec le bon démarrage du tuner, tuner en FM et en AM (bibliothèque PU2CLR SI4735, MIT), son du tuner mesuré par l'ESP32, ampli. Il annonce chaque essai en français sur le port série, pose une question, et donne un bilan. Compilé le 23/10/2026 sans erreur ni avertissement ; pas encore essayé sur une vraie carte.
    - `outils/mesures_guidees.py` déroule les mesures des étapes 2 à 4 avec le banc : il dit dans quels entonnoirs mettre les pointes, lit la valeur sur le multimètre par sigrok (logiciel libre, beaucoup de multimètres) ou la fait taper, dit si elle est bonne, s'arrête là où le plan de test le demande, et range tout dans un fichier daté. Les valeurs attendues sont dans `cartes/NOM-mesures.json`.
14. **Faire relire la carte par un électronicien : le dossier de relecture** (`dossier_relecture.py`, étape 7 de la commande, environ 15 secondes).
    - Le script réunit tout ce qu'il faut dans `resultats/NOM/dossier-relecture/`, et dans un zip à côté (radio v4 : 1,5 Mo) :
      - un mot d'accompagnement : le projet, ce qui est demandé, le temps estimé, ce qui est déjà vérifié, ce que les outils ne peuvent pas vérifier, la liste des fichiers ;
      - la fiche de questions ;
      - le schéma ;
      - la carte couche par couche (kicad-cli) ;
      - l'image 3D ;
      - le plan de test ;
      - les bilans des contrôles ;
      - le projet KiCad à ouvrir, sans les modèles 3D ;
      - les fichiers de fabrication.
    - Les PDF tirés du texte sont balisés (PDF/UA, par pandoc et LibreOffice) : titres, listes, langue française, titre du document. Ils se lisent aussi au lecteur d'écran. C'est un cas gratuit pour la graine « outil PDF accessible ». Le balisage est vérifié par pdfinfo et par la structure du fichier ; aucun validateur PDF/UA complet n'a tourné.
    - Le texte propre à la carte (auteur, présentation, temps estimé) est dans `cartes/NOM.json`, rubrique « relecture ».
    - **Rien n'est envoyé par la chaîne.** Kévin choisit à qui il écrit, et envoie lui-même.
    - Premier essai du 24/10/2026 : demande préparée pour la délégation Ain-Rhône d'ECTI (retraités bénévoles). ECTI travaille surtout avec des entreprises, des collectivités, l'éducation et l'insertion ; l'électronique n'est pas citée, et une « participation forfaitaire » est demandée, sans montant publié. C'est un essai, pour voir ce que ça vaut.

## Installer les logiciels ailleurs

Les logiciels de la chaîne ne sont pas dans les zips : seuls les scripts et les données y sont. Pour les réinstaller :
- sur Ubuntu 24.04 : `bash installer-ubuntu.sh`, qui reprend les versions essayées le 22/10/2026 ;
- avec Docker : `docker build -t chaine-puzzle .`, puis `docker run`. Le mode d'emploi est en tête du `Dockerfile`.

Essai du 23/10/2026, dans l'espace de travail de Claude :
- l'image Docker se construit en 5 min 40 à partir d'une Ubuntu 24.04 neuve. Elle fait 4,4 Go ;
- la chaîne y tourne de bout en bout, coupée du réseau, en 7 minutes, avec les mêmes résultats.

Pour l'essai, une seule chose a été ajoutée, et elle n'est pas dans la recette : le certificat du proxy réseau de cet espace de travail. Le script Ubuntu n'a pas été lancé seul, hors de Docker, mais c'est lui que le Dockerfile exécute.

## Ce que chaque outil fait bien et mal (constaté le 22/10/2026)

- **EasyGerber**
  - Bien : rapide et propre sur un bloc de 10 à 30 composants.
  - Mal :
    - il refuse les grandes cartes ;
    - son propre contrôle dit « OK » même quand il y a des erreurs. Constaté : une piste à 0,016 mm d'une broche, une alimentation 5 V en piste de 0,22 mm pour 1,5 A, un plan 3,3 V étranglé ;
    - il ne connaît pas la zone de l'antenne.
- **Freerouting**
  - Bien : il trace proprement les liaisons entre les sorties.
  - Mal :
    - il ignore la limite du nombre de passes en ligne de commande (environ 5 minutes par carte) ;
    - sans consignes, il coupe les plans d'alimentation ;
    - il ajoute aussi du cuivre sur des réseaux déjà complets, et laisse des bouts de piste qui ne mènent nulle part. La chaîne les enlève.
- **KiCad 7**
  - Bien : un contrôle fiable, et un fichier ouvert, aux normes.
  - Mal : il ne sait pas reprendre en script le travail de Freerouting. Remplacé par KiCad 10.

- **easyeda2kicad**
  - Bien : il donne les vraies empreintes et les modèles 3D. Il a confirmé celles d'EasyGerber (écart de 0,01 mm au plus) et le brochage de la prise USB-C, broche par broche.
  - Mal : leur sérigraphie déborde sur les pastilles. C'est sans effet, l'usine l'efface, mais KiCad la signale.
- **ngspice**
  - Bien : il calcule ce que les contrôles de dessin ne voient pas.
- **KiCad 10** (10.0.7, installé depuis la source officielle, clé vérifiée)
  - Bien :
    - le contrôle en ligne de commande (`kicad-cli pcb drc`) donne un rapport lisible par script ;
    - il sait faire une image 3D de la carte (`kicad-cli pcb render`) ;
    - il ramène lui-même le résultat de Freerouting en gardant les pistes des blocs. Testé : `import_ses.py` peut être retiré.
    - ses classes de réseaux passent toutes seules dans le fichier pour Freerouting, avec leur largeur de piste. Plus besoin de retoucher ce fichier à la main ;
    - un fichier de règles en plus (`carte.kicad_dru`) lui apprend ce que ses réglages de base ne savent pas dire : JLCPCB demande 0,28 mm entre un trou métallisé et le cuivre d'un autre réseau.
  - Mal :
    - en script, après avoir enlevé une piste, il faut utiliser `board.Delete` et non `board.Remove`, sinon la liste des pistes devient illisible ;
    - l'interface Python qu'utilise la chaîne (« SWIG ») sera retirée dans KiCad 11. Il faudra passer à la nouvelle (`kicad-python`), qui marchera sans fenêtre à partir de KiCad 11 ;
    - ses « blocs de conception » (un bloc routé qu'on réutilise) ne se pilotent pas en commande, d'après ce que j'ai trouvé. La bibliothèque de blocs de la chaîne fait ce travail en attendant.
  - Il a montré que les règles de fabrication de JLCPCB n'étaient pas enregistrées dans le projet. Elles le sont maintenant : écart 0,1 mm, trou 0,15 mm, bord 0,2 mm.
- **KiKit** (1.8.1, avec Python 3.12)
  - Bien : il produit les fichiers Gerber pour JLCPCB. Mon contrôle indépendant donne exactement les mêmes résultats sur ses fichiers.
  - Limite : pour la liste des composants et le placement, il lui faut un schéma KiCad, que la chaîne ne produit pas encore. La chaîne reprend donc ceux d'EasyGerber.

## Règles apprises

- Une carte a un niveau de confiance, écrit dans sa fiche de questions : « contrôlée par la chaîne », puis « relue par un électronicien », puis « essayée sur prototype ». On ne dit pas qu'une carte est bonne avant le troisième.
- Pour chaque carte, une fiche de questions pour l'électronicien (`cartes/NOM-questions-electronicien.md`) liste ce que la chaîne n'a pas pu vérifier. Les réponses, avec la date et la personne, reviennent dans cette méthode : c'est comme ça que la chaîne apprend du réel.
- Vérifier le stock des pièces dès qu'on les choisit, avant de router un bloc. Constaté le 23/10/2026 : le bloc tuner avait été fait autour du Si4735, qui n'était plus en stock.
- Un trou de fixation entre deux blocs peut empêcher une liaison. Constaté le 23/10/2026 : avec deux trous dans le couloir entre l'alimentation et l'ampli, Freerouting n'a pas pu relier le 5 V en trois passages. La recherche automatique des trous évite maintenant les couloirs entre blocs ; la carte radio a grandi de 7 mm en haut pour les accueillir.
- Pour une lecture au toucher, garder l'ordre : des rangées alignées, de gauche à droite et de haut en bas, quitte à sauter une place. Constaté sur le banc de test : en cherchant la place libre la plus proche, les numéros 6, 7 et 12 s'étaient retrouvés en désordre.
- Un point braille en demi-sphère laisse un maillage ouvert à son sommet (le pôle) : la pièce n'est plus « fermée » pour l'impression. Un petit cylindre aux bords bien arrondis ne pose pas ce problème.
- Un contrôle qui ne trouve rien peut être un contrôle aveugle. Constaté le 24/10/2026 : l'ERC de KiCad disait « aucune erreur », avec 130 avertissements, parce que les broches n'avaient pas de type. Pour savoir si un contrôle voit vraiment, on casse exprès une copie de la carte et on regarde s'il le dit. Corrigé le jour même : types repris de la bibliothèque officielle de KiCad ; trois erreurs volontaires, toutes trois vues.
- Une étape qui plante doit se voir autant qu'une erreur de contrôle. Constaté le 24/10/2026 :
  - en version 1.16, la maquette est passée au braille de liblouis ; les points avaient été vérifiés sur tous ses textes, mais l'étape n'avait pas été relancée en entier ;
  - une ligne parlait encore de l'ancienne table « BRAILLE » : l'étape 4 plantait au bout d'une minute, et la chaîne écrivait quand même « Terminé », avec le code de sortie 0 ;
  - les maquettes des paquets 1.16 à 1.20 venaient du dernier passage qui marchait ; elles allaient avec la carte de ces paquets ;
  - corrigé : la chaîne relit ses scripts avant de partir (pyflakes aurait vu l'erreur en une seconde), signale toute étape plantée et rend le code 2.
- Après un changement dans un script, relancer l'étape entière, pas seulement la partie changée.
- Une empreinte partagée entre plusieurs pièces garde les champs de la première pièce téléchargée. Les champs d'un composant (référence LCSC, MPN, fabricant) se prennent sur la pièce elle-même, jamais sur sa bibliothèque.
- Regarder le résultat comme le verrait une personne, pas seulement le calculer. Constaté le 23/10/2026 sur le boîtier : tous les contrôles de forme passaient, mais l'image du dessus vue d'en haut montrait des noms décalés de 3 mm, collés aux boutons, et un mot qui sortait du bord. Le contrôle des noms fait maintenant partie de l'étape.
- Mesurer la distance au bord sur le vrai contour, coins arrondis compris. Corrigé le 23/10/2026 : le contrôle indépendant mesurait sur un rectangle et donnait 0,30 mm ; la vraie distance est 0,20 mm, près d'un coin. C'est juste à la limite de JLCPCB (0,2 mm), mais c'est bon.

- Toujours des sorties au bord des blocs.
- Choisir les broches du microcontrôleur pour que rien ne croise la paire USB.
- Mettre les prises (USB, antenne) au bord de la carte, quitte à tourner un bloc.
- Ne jamais croire le contrôle d'EasyGerber seul.
- Rien de propre à une carte dans le code : tout va dans les fichiers de description.
- Les vias de Freerouting font 0,7 mm pour un trou de 0,3 mm. Avec 0,6 mm, un via s'est retrouvé à 0,25 mm du 5 V. Seul le contrôle indépendant l'a vu ; KiCad l'a vu aussi une fois la règle ajoutée.
- Freerouting ne donne pas deux fois le même routage : chaque passage de la chaîne doit être contrôlé en entier.
- Un bloc emporte ses contraintes (zone d'antenne, courants) : elles le suivent quand on le déplace ou le tourne.
- Quand on dispose les blocs, les sorties de chaque bloc doivent faire face aux blocs qu'elles rejoignent, jamais au bord de la carte. Constaté sur la variante compacte : ampli posé avec ses sorties vers le bord, et le 5 V n'a pas pu être relié.

## Pistes trouvées sur hackaday.io pour ce que la chaîne ne sait pas encore faire (23/10/2026)

Deux choses que la chaîne ne faisait pas, trouvées sur hackaday.io et confirmées chacune par plusieurs autres sources. Le boîtier est devenu l'étape 11 (version 1.14), le banc de test l'étape 12 (version 1.15), à la demande de Kévin.

**1. Le boîtier, fabriqué à partir de la carte.**
- Outil : **YAPP_Box** (« Yet Another Parametric Projectbox », Willem Aandewiel, licence MIT), pour OpenSCAD. Maintenu : version 3.3.8 d'août 2025.
- Sources : un projet sur hackaday.io (Ventbot, WJCarpenter, qui a pris les cotes dans KiCad), un article de hackaday.com (2022), le dépôt GitHub, sa documentation et un guide Instructables.
- Essai du 23/10/2026 sur la radio v4, avec OpenSCAD 2021.01 :
  - le boîtier sort en 2 secondes, en deux pièces fermées : un fond de 86 × 72 × 9 mm et un couvercle de 86 × 72 × 12 mm ;
  - les ouvertures de la prise USB-C et de l'antenne FM traversent bien les parois au bon endroit (vérifié en lançant des rayons à travers le modèle), avec trois petits trous dans le couvercle pour RESET, BOOT et la LED ;
  - les positions viennent de la carte KiCad ; la hauteur de la prise d'antenne est estimée.
  - Rien n'est imprimé.
- Constat : **la carte radio v4 n'avait aucun trou de fixation**. Ajoutés en version 1.15 (voir l'étape 5).
- Fait en version 1.14 : voir l'étape 11.

**2. Le banc de test à pointes.**
- C'est un support imprimé où l'on pose la carte : des pointes à ressort touchent les sorties par dessous. Plus besoin de viser une pastille de 1,5 mm avec la pointe du multimètre : chaque pointe est reliée par un fil à une borne repérée en relief.
- Sources :
  - gCore (Dan Julio, hackaday.io) : banc pour la fabrication en série, avec support imprimé et pointes à ressort ;
  - wESP32 (hackaday.io) : cartes testées en fabrication en les posant sur des pointes ;
  - OpenFixture : article de hackaday.com (2016), dépôt GitHub (dernière modification en 2017), version reprise en 2021 sur le forum KiCad ;
  - pogojig (jaseg, 2019, présenté sur EEVblog) : même auteur que gerbonara, que la chaîne utilise déjà ;
  - open_jig (pglab, pour FreeCAD).
- Le principe est concordant, mais les outils sont anciens (2017, 2019), et pogojig demande de dessiner les pointes à la main dans Inkscape. La chaîne a déjà les briques : les positions des 19 sorties, lues dans KiCad, et CadQuery, qui fait déjà la maquette. Le banc se ferait donc avec elles plutôt qu'en reprenant ces outils.
- Il faut des pointes à ressort, à acheter (pas commandées).
- Fait en version 1.15 : voir l'étape 12. Kévin a choisi une petite carte du banc plutôt que des fils soudés à la main.

## Pistes trouvées dans des coins peu connus (23/10/2026)

Recherche sur GitHub, GitLab universitaires, la liste des développeurs KiCad, des articles ACM, le Smith-Kettlewell Technical File. Rien n'est encore branché ; les quatre premières pistes ont été rouvertes et vérifiées.
- **Senhor Placo Circuito** (sr-placo-circuito, MIT, 3 commits, un seul auteur) : un flux KiCad avec Claude Code pour un concepteur aveugle, avec une pièce tactile où chaque élément a sa hauteur (plans en creux, pistes en arêtes fines, pastilles basses, broche 1 en tour) et l'orientation donnée par les trous de fixation. Le plus proche de la chaîne puzzle : idées à reprendre pour la maquette, et un contact possible.
- **hwcontract** (MIT) : juge une capture sigrok ou un journal série contre un « contrat » YAML (PASS, MARGINAL, FAIL, MISSING), en texte ; aussi serveur MCP. Pour juger la sortie du programme d'essai et, plus tard, des signaux.
- **kicad-mcp-server** (Seeed Studio, MIT, KiCad 10) : interroger une carte KiCad en conversation (« à quoi est reliée la broche 5 de U3 ? »), contrôles par kicad-cli.
- **Smith-Kettlewell, « Non-Visual Soldering Techniques »** (page mise à jour le 14/04/2026) : souder sans la vue ; utile aussi à la graine « poste électronique accessible ».
- Non revérifiées, à regarder : QEMU d'Espressif (faire tourner le programme d'essai sans carte, mais sans I2C) ; multimètre parlant libre pour l'Owon B16 (fablab de Betton, lié à My Human Kit ; licence ambiguë) ; CamIO-Web (Université de Milan : faire parler une maquette touchée, avec la caméra du téléphone) ; STRAUSS et Chart2Music (transformer des mesures en son : graine « oscilloscope accessible ») ; le guide « Tactile Schematics » (règles pour des schémas lisibles au doigt) ; un fil de juin 2026 sur la liste des développeurs KiCad, sur l'accessibilité de KiCad aux lecteurs d'écran.
- Pas trouvé : un oscilloscope ou un analyseur logique accessible, libre et entretenu ; un outil de placement de composants accessible.

## Pistes trouvées ailleurs (23/10/2026, deuxième recherche)

Recherche dans les forums non anglophones (allemands, français, japonais, chinois), les archives ouvertes (HAL, theses.fr, Zenodo, arXiv), la Fab Academy, Printables et les associations de radioamateurs aveugles. « Rouvert » veut dire que Claude a rouvert la page lui-même ; le reste vient du rapport de recherche et n'a pas été revérifié. Rien n'est encore branché dans la chaîne.

Pour la chaîne :
- **Braille en bosses de soudure sur la carte elle-même** (rouvert : article hackaday.com du 29/08/2025, qui renvoie à un article de 2017). Des pastilles rondes sans vernis, posées en cellules braille ; l'étain fondu fait les bosses. Une personne, Tara, en a mis sur des cartes d'essai pour une élève aveugle ; c'est encore un prototype. Aucun générateur pour KiCad trouvé. Pour la chaîne : liblouis (déjà là), puis une empreinte de pastilles sans vernis, pour repérer au doigt les prises et la broche 1 sur la vraie carte. À essayer au TactiLab avant de le mettre sur une carte à commander. La hauteur des bosses (0,6 mm d'après le rapport) n'est pas dans l'article rouvert.
- **Stencilframer** (Igor Brkić, Croatie ; rouvert : article de l'auteur). Python et OpenSCAD, déjà dans la chaîne : lit le contour d'un .kicad_pcb (KiCad 6 et plus) ou d'un Gerber, et fait un support à imprimer qui tient la carte et le pochoir alignés, pour poser la pâte à braser sans viser à l'œil. Code sur bitbucket.org/igor_b/stencilframer. Licence MIT d'après le rapport, pas écrite dans l'article. Pas essayé avec KiCad 10. Utile seulement si la carte est assemblée à la main.
- **KiCad Pinout Generator** (Charles Grassin, France ; rouvert : MIT). Sort le brochage d'un composant depuis la carte routée : tableau, CSV, ou code C, Python, Rust. Pourrait contrôler `broches_esp32.py`. La page ne parle que de la fenêtre de KiCad ; le lancer par script n'est pas vérifié, ni KiCad 10.

Pour les mesures (étape 13 et graine « oscilloscope accessible ») :
- **lxi-tools** (rouvert : BSD-3). Commande en ligne pour les appareils de mesure en réseau : `lxi discover`, `lxi scpi` (une question, une valeur en texte), `lxi screenshot`, scripts Lua. Testé par l'auteur sur Rigol, Siglent, Rohde & Schwarz, Keysight, Tektronix et d'autres. Tout appareil de table en réseau devient lisible à la voix ou en braille. PyMeasure (Python, MIT) fait la même chose, d'après le rapport.
- **Alimentation Riden RD6006 et module Python `rd6006`** (rouvert : Apache-2.0). Par USB : régler tension et limite de courant, allumer ou couper, lire tension, courant et puissance. Ça permettrait une première mise sous tension guidée : courant limité, courant dit à voix haute, coupure si ça dépasse. Appareil à acheter (pas commandé).
- **Multimètre de table Owon XDM1041** et `owon-xdm1041-server` (MIT, projet très jeune ; non rouvert). Le rend lisible en réseau, aussi par lxi-tools.

Pour souder sans la vue (graine « poste électronique accessible ») :
- **Nanao, « How to solder without vision »** (rouvert : 7oh.dev, 23/09/2026). Composants traversants seulement. L'étain passe dans un tube inox fin (1,5 mm dehors, 1,2 mm dedans) tenu par une pince à bras articulé ; on sent la vibration quand le tube touche la broche ; contrôle au toucher (la soudure ne bouge plus) et au testeur de continuité pour les ponts. L'article ne dit pas si l'auteur est aveugle. Un deuxième blog japonais (watakatsu.com, non rouvert) ajoute une butée pour doser l'étain. Le porte-tube s'imprime en 3D.
- **Fer Pinecil V2 et `pynecil`** (rouvert : MIT). Par Bluetooth : lire l'état du fer et régler la consigne (exemple : 350 °C). La page ne détaille pas les valeurs lues. Il faudrait l'interroger régulièrement pour faire dire « fer chaud, prêt ».

Pour RADIONÉO :
- **UNARAF**, Union nationale des aveugles radioamateurs de France (rouvert : unaraf.fr). Président : Tony, F5ANZ. Active en 2026 (station portable à Valloire les 19 et 20/09/2026). Contact par le formulaire du site. Des testeurs et des partenaires possibles pour un poste de radio conçu sans la vue. Ne rien leur écrire sans l'accord de Kévin.
- **ARRL, instruments audibles** (non rouvert) : des montages publiés dans QST de 1979 à 1998 pour radioamateurs aveugles (cadran lu par des sons, wattmètre parlant, accord d'antenne à l'oreille). Lecture libre, reproduction interdite.

Cherché sans rien trouver : forums allemands, français et japonais sur la conception de cartes sans la vue ; HAL, theses.fr, Zenodo, arXiv (les travaux de l'IRIT portent sur les cartes géographiques tactiles) ; un four de refusion ou un outil de placement libre utilisable sans écran.

## Pistes trouvées partout (23/10/2026, troisième recherche)

Trois recherches menées en même temps : lire une carte sans la vue ; les trous de la chaîne ; les personnes, les lieux et les financements. « Rouvert » veut dire que Claude a rouvert la page lui-même ; le reste vient des rapports de recherche. Rien n'est encore branché.

### À retenir tout de suite

- **Rester sur KiCad 10.0.x.** Rouvert : page des développeurs de KiCad, PyPI, ticket KiKit n° 814.
  - Le module `pcbnew` (SWIG) doit disparaître avec KiCad 11. Huit scripts de la chaîne l'utilisent : `assembler`, `freerouter`, `schema`, `fabricants`, `maquette`, `boitier`, `banc_test` et `modeles3d`.
  - Son remplaçant, kicad-python (MIT, version 0.8.0 du 30/08/2026), ne marche aujourd'hui qu'avec KiCad ouvert.
  - KiKit attend un mode sans fenêtre pour être porté, sans date annoncée.
  - La date de sortie de KiCad 11 n'est pas vérifiée.
  - À faire avant KiCad 11 : regrouper les appels à `pcbnew` dans un seul module de la chaîne, pour tout adapter d'un coup.

### Pour la chaîne

- **pytest-embedded** (Espressif ; rouvert)
  - Ce que c'est : un greffon pour pytest. Il programme la carte, lit le port série et attend des messages précis. Ses modes sont `arduino`, `serial`, `esp`, `wokwi`, `qemu` et `espemu` : le même test tourne sur la carte, dans Wokwi ou dans l'émulateur d'Espressif.
  - Pour l'étape 13 : remplacer les réponses « o » ou « n » tapées à la main par des vérifications automatiques, et y mettre les mesures sigrok.
  - Licence MIT d'après le rapport ; elle n'est pas écrite sur la page rouverte. Effort petit à moyen.
- **Wokwi** (rouvert)
  - Ce que c'est : un simulateur d'ESP32-S3 en ligne. Une « puce personnalisée » écrite en C peut jouer le tuner sur le bus I2C (fonctions `i2c_init`, `connect`, `read`, `write`).
  - Limites : service fermé. L'offre gratuite « Community » est réservée aux projets libres, et en projets publics seulement. La page des prix ne dit pas si les puces personnalisées et les minutes de test automatique en font partie.
  - Le code de la radio partirait sur leurs serveurs.
- **esp-emulator d'Espressif** (rouvert ; Apache-2.0 ; en bêta)
  - Ce que c'est : un émulateur qui tourne sur l'ordinateur, gratuit et sans Internet. Il prend en charge l'ESP32-S3.
  - Limites : il est documenté pour des programmes ESP-IDF ; Arduino et PlatformIO ne sont pas confirmés. En I2C, il n'imite qu'une mémoire EEPROM intégrée, pas un faux tuner.
- **pcb-dfm** (rouvert ; Apache-2.0 ; une seule source)
  - Ce que c'est : 65 contrôles de fabrication sur les Gerbers (couronnes, pièges à acide, équilibre du cuivre, vernis, sérigraphie, etc.). Il s'appuie sur gerbonara, comme le contrôle indépendant. Sortie en texte, JSON ou HTML.
  - Limites : l'auteur prévient qu'environ la moitié des contrôles sont des approximations, et que les seuils ne viennent pas des fabricants. Il ne peut que compléter le contrôle indépendant, jamais le remplacer.
- **kicad-happy** (rouvert ; MIT ; KiCad 5 à 10)
  - Ce que c'est : des compétences Claude pour relire un schéma et une carte, avec les règles JLCPCB et PCBWay et une recherche LCSC sans clé.
  - À essayer pour relire un bloc avant EasyGerber. La page se contredit sur le numéro de version.
- **Placement automatique** : toujours pas de placeur libre et fiable.
  - Quilter (rouvert) place et route. Il est gratuit en dessous de 10 personnes et de 50 000 $ de revenus, mais en échange il se sert des cartes pour entraîner son moteur. À éviter pour une invention pas encore protégée.
  - DeepPCB (InstaDeep) : payant, avec une API. Non rouvert.
- **Non rouverts** : KiCost avec les clés Mouser, Nexar ou TME (prix en Europe) ; le greffon « Push » et l'assemblage d'AISLER.
- **Rien trouvé** : Renode (pas d'ESP32-S3) ; des règles d'Eurocircuits, de Proto-Electronics ou de Beta Layout lisibles par un programme.

### Lire une carte ou une mesure sans la vue

- **Afficheurs tactiles de 60 × 40 picots** (rouvert). Les deux permettraient d'afficher un bloc ou une couche de cuivre en quelques secondes, sans rien imprimer. Ils sont chers : à essayer là où il y en a un, pas à acheter.
  - Graphiti (Orbit Research) : picots de hauteur variable, surface tactile, entrée HDMI, USB et Bluetooth, « API ouverte ». La bibliothèque sur GitHub (C, C++, Java, Python) est faite pour Windows. Sa licence est floue : le fichier est sous GPL, mais la page dit « tous droits réservés ». Prix non publié.
  - Dot Pad (Dot Inc.) : 60 × 40 picots et 20 cellules braille, USB-C et Bluetooth. Il marche avec NVDA sous Windows 11 et avec VoiceOver (RNIB, 02/2025). Il existe des kits de développement pour Web, Android, iOS, Windows et Linux. La page rouverte ne montre ni la fonction d'affichage d'image ni la licence.
- **Papier thermogonflé** : des règles chiffrées.
  - Monica Houston (Hackster, 05/03/2023, GPL-3.0+ ; rouvert) passe de Fritzing au papier gonflé :
    - le trait le plus épais est ramené à 1,3 mm ;
    - 6 mm de vide autour de chaque composant ;
    - des pistes droites, à angle droit ;
    - le braille à 6 mm de son objet ;
    - de l'encre noire au carbone.
  - Le manuel BANA des dessins tactiles (non rouvert) donne aussi des règles.
  - Aucune chaîne toute faite ne va de KiCad au papier gonflé. La chaîne pourrait sortir un SVG qui suit ces règles : c'est bien plus rapide qu'une maquette imprimée en 3D.
- **RUDO** (Milan Hudec, Slovaquie ; rouvert : article de 2019)
  - L'auteur est un chercheur aveugle. Son multimètre parle. Son oscilloscope envoie l'image de l'écran, et le logiciel dit en mots le type de courbe (sinus, carrée, dent de scie), la fréquence, l'amplitude et les déformations : 80 % des courbes reconnues en un an d'essai.
  - Écrit en Free Pascal, tourne sous Debian. « Pas de restriction de licence », mais aucune licence n'est nommée.
  - Graine « oscilloscope accessible ».
- **AccessibleCircuits** (CHI 2021, Dartmouth et Université nationale de Taïwan ; rouvert)
  - Des pièces imprimées pour une planche d'essai. Un téléphone dit la colonne qu'on touche, et vibre quand la patte est bien enfoncée.
  - Avec 10 participants aveugles : 20 % de composants bien enfoncés sans les pièces, 86 % de circuits simples réussis avec.
  - TangibleCircuits fait un modèle tactile et sonore à partir d'un fichier Fritzing.
  - Fichiers non publiés. Graine « poste électronique accessible ».
- **Glasgow, applet `curve-trace`** (rouvert) : trace en ligne de commande la courbe tension-courant d'une diode ou d'une LED, en CSV. Permet de vérifier un composant en texte, ou à l'oreille avec Chart2Music. Matériel à acheter.
- **Bus Pirate 5** (rouvert ; MIT) : un outil série piloté au clavier. Il a une alimentation de 1 à 5 V avec limite de courant, mesure la tension sur ses broches et parle I2C. De quoi parler au Si4732 seul, sans l'ESP32. Le mode sans couleurs pour lecteur d'écran n'est pas confirmé.
- **Brevets sur l'écoute des mesures**
  - US 8 803 560 (Boeing ; rouvert) : déposé en 2008, accordé en 2014. Il protège un appareil où la hauteur du son donne la valeur, et deux timbres le signe (plus ou moins), avec un trémolo.
  - C'est un brevet américain : il ne s'applique pas en France. Sa date de fin n'est pas vérifiée.
  - D'après le rapport, d'autres plus anciens sont expirés : US 5 020 108 ; US 3 914 800, un « oscilloscope tactile » à jet d'eau.
  - À connaître avant une enveloppe Soleau pour l'oscilloscope accessible. Ce n'est pas un avis juridique.
- **Rien trouvé** : une chaîne de KiCad vers un afficheur ; un oscilloscope parlant du commerce encore suivi ; HyperBraille (le site de Metec est détourné).

### Personnes, lieux, financements

- **Vision Participative** (rouvert : appel à communication relayé par la FIRAH)
  - Une demi-journée d'étude à Lyon, le 30 novembre 2026 après-midi : « Déficiences visuelles et recherches participatives : point de vue des jeunes chercheuses et chercheurs ».
  - Ouverte à tous, gratuite, inscription obligatoire. Contact : vision-participative-contact@listes.univ-eiffel.fr.
  - C'est un réseau de chercheurs et d'acteurs de terrain, de l'Université Gustave Eiffel. Le lieu exact n'est pas trouvé : leur site refuse les robots.
- **Fabrique d'Objets Libres** (fablab associatif du Grand Lyon)
  - Rouverte à la MJC Louis Aragon de Bron depuis début septembre. Rouvert : La Rayonne, et un billet du fablab du 22/07/2026 vu dans les résultats de recherche.
  - Horaires d'après le rapport, non revérifiés : mercredi de 14 h à 17 h, jeudi de 18 h à 21 h.
  - Le matériel d'électronique est à demander sur place.
- **Fil « rendre KiCad accessible »** (liste des développeurs de KiCad, 16 et 17/06/2026 ; rouvert)
  - Un étudiant aveugle propose de rendre KiCad lisible par les lecteurs d'écran.
  - Seth Hillbrand, développeur principal, demande d'abord une proposition écrite, et des bibliothèques à licence compatible GPL. KiCad travaille déjà à des menus et des dialogues lisibles par les lecteurs d'écran.
  - Kévin pourrait proposer d'essayer. Graine « banc d'essai des lecteurs d'écran ».
- **Région Auvergne-Rhône-Alpes, « Innover pour compenser le handicap »** (rouvert : fiche Infogreffe)
  - Pour les associations, communes et entreprises de la région, pas pour les particuliers : il faudrait passer par une association partenaire.
  - De 20 à 50 % des dépenses d'investissement (au moins 500 €, logiciels spécialisés compris), plafond 100 000 €. Le projet doit être local et construit avec les usagers.
  - Contact : handicap@auvergnerhonealpes.fr.
- **A11yShape** (rouvert : arXiv, août 2025) : OpenSCAD et une IA pour des programmeurs aveugles (descriptions des modèles, versions, vue en arbre). Proche de ce que fait la chaîne pour le boîtier. Code non publié.
- **Non rouverts** : la liste blind-hams (groups.io, en anglais ; page inaccessible) ; Program-L ; ACCESS@KIT (Karlsruhe, afficheurs tactiles) ; des forums pour faire relire une carte (forum KiCad, EEVblog, Futura-Sciences).
- **Pas adaptés** :
  - NLnet Restack : date limite le 03/11/2026, mais le thème est Internet, et l'accessibilité n'en fait pas partie ;
  - Handitech Trophy 2026 : fermé ;
  - Prototype Fund : Allemagne seulement ;
  - l'aide de l'Agefiph : il faut créer une entreprise.

## Pistes trouvées pour les erreurs que l'ERC ne voit pas (24/10/2026)

Recherche dans les tickets GitHub et GitLab, le forum KiCad, les forums japonais, chinois et allemands, et la recherche. « Rouvert » veut dire que Claude a vérifié lui-même.
- **Le constat** :
  - Le mainteneur d'easyeda2kicad refuse de deviner les types de broches (ticket n° 74, rouvert) : un type faux serait pire qu'aucun.
  - JLC2KiCadLib recopie aussi le champ vide.
  - EasyEDA Pro n'exporte pas vers KiCad.
  - D'après le code de KiCad 10, lu par la recherche : une broche « non définie » fait un avertissement avec n'importe quelle autre, et les contrôles « non alimenté » l'ignorent.
- **Retenu et branché** : les types de la bibliothèque officielle de KiCad (rouvert : les symboles de l'ESP32-S3, de l'AMS1117, de l'USBLC6, du PAM8403D et de la prise USB-C y sont ; le Si4732 n'y est pas, les Si4730 à Si4735 oui), et la parité schéma ↔ carte de KiCad (rouvert : `kicad-cli pcb drc --schematic-parity`).
- **À regarder** (rouverts le 24/10/2026, pas encore essayés) :
  - **kicad-happy** (Andrew Klofas, MIT ; version 2.3.2 du 22/10/2026 ; KiCad 5 à 10).
    - Ce que c'est : des scripts Python sans dépendance (`analyze_schematic.py`, `analyze_pcb.py`, `cross_analysis.py`…), qui marchent seuls, sans KiCad, et des compétences pour Claude.
    - Ce qu'il ajouterait : des contrôles de valeurs, que `controle_circuit.py` ne fait pas. Par exemple : la capacité de charge d'un quartz, le temps de montée du bus I2C avec la valeur des tirages, la tension des condensateurs, la puissance des résistances, les protections contre les décharges.
    - D'après la recherche, il devine une partie des choses d'après les noms des liaisons, et dépend lui aussi des types de broches.
    - Pas lancé : le 24/10/2026, le garde-fou de l'espace de travail de Claude a refusé trois fois d'exécuter ce code téléchargé, dont deux fois après l'accord écrit de Kévin. L'accord donné dans la conversation ne suffit pas à le débloquer. Pour le lancer pour de vrai : sur les machines de GitHub, dans un dépôt privé de Kévin. Le réglage est prêt : `.github/workflows/kicad-happy.yml` (version de kicad-happy épinglée, droits en lecture seule, un dossier de résultats par carte). Le garde-fou refuse aussi que Claude crée le dépôt (« partage de données ») : Kévin crée le dépôt vide `chaine-puzzle` (privé), puis Claude y envoie la chaîne.
    - Ses contrôles ont été refaits à la main sur la radio v4, d'après sa documentation (`methodology_schematic.md`), le 24/10/2026 :
      - le quartz : deux 22 pF pour un quartz prévu pour 12,5 pF donnent environ 14 pF. Skyworks fait exactement pareil dans sa note AN299 : pas une erreur ;
      - la tension des condensateurs : tous tiennent au moins 25 V, sur des liaisons de 5 V au plus ;
      - les tirages I2C : 4,7 kΩ vers le 3,3 V, bon ; la mise en route de l'ESP32-S3 : 10 kΩ et 1 µF, comme le recommande Espressif ;
      - nouveau : 33 µF sur VBUS, alors que la règle de l'USB 2.0 en permet 10 (question 11 de la fiche) ;
      - nouveau : pas de place pour les résistances en série sur D+ et D-, que le guide d'Espressif recommande de prévoir (question 12 de la fiche).
  - **KiPart 2.8.0** (MIT, 08/08/2026, PyPI).
    - Ce que c'est : fabrique un symbole KiCad depuis un tableau CSV ou Excel, avec une colonne « Type » pour le rôle de chaque broche.
    - Il a aussi `kilib2csv` (un symbole en tableau), `cmpparts` (compare deux bibliothèques) et un serveur MCP (`kipart-mcp`).
    - Utile pour faire un vrai symbole du Si4732, depuis le tableau des broches de sa fiche, au lieu d'emprunter les types du Si4735.
  - **akcli** (akcli-kicad 0.22.0 du 25/08/2026, MIT, un seul auteur).
    - Ce que c'est : un outil en ligne de commande pour faire et contrôler un schéma KiCad, sans KiCad. Sa commande `check` fait un « ERC allégé », plus l'alimentation, la liste des pièces et des « contrats ».
    - Sa commande `jlc` convertit une pièce LCSC « avec des broches typées », mais la page ne dit pas d'où viennent les types : à vérifier avant de s'y fier.
    - Projet jeune, d'une seule personne.
  - **check_symbol.py** (règles KLC, non rouvert) : il signale les types faux, mais ne les corrige pas.
- **Regardés, pas utiles maintenant** :
  - **KiBot** (version 1.9.1, juillet 2026, KiCad 10 pris en charge ; rouvert). Il fait d'un coup les contrôles et les fichiers de sortie de KiCad. La chaîne a déjà KiKit et kicad-cli pour ça ; KiBot ajouterait une couche sans rien contrôler de plus.
  - **KiPilot** (serveur MCP, alpha de mai 2026 ; rouvert). Il lit et modifie une carte en conversation, mais il faut KiCad ouvert à l'écran : pas utilisable sans la vue, ni sans fenêtre.
- **Rien trouvé** : un outil libre qui vérifie de façon générale « broche SDA sur liaison SCL ». D'où `controle_circuit.py`, petit et lisible.

## Pistes pour une bibliothèque de blocs plus rapide, et une chaîne toute libre (24/10/2026)

Le constat de Kévin : faire seuls tous les blocs prendrait trop longtemps (on ne fait pas quinze projets par jour), et EasyGerber n'est pas libre. Le but : une chaîne toute libre, utile à tout le monde. Rien n'est encore essayé.
- **Les blocs de KiCad 10** (rouvert : annonce officielle de KiCad 10, mars 2026 ; deux fils du forum KiCad en parlent). KiCad rangeait déjà des blocs de schéma (« design blocks »). Depuis la version 10, il range aussi des blocs de carte : « Users can now create and manage libraries of board layouts ». C'est l'idée des blocs de la chaîne, dans le format de KiCad, qui est libre. À essayer : ranger nos 4 blocs comme blocs KiCad. Pas vérifié : si le routage du bloc est gardé, et si on peut les poser par script.
- **Reprendre des blocs dans des montages publiés**, contrôlés par la chaîne avant d'être acceptés, avec leur licence notée :
  - le jeu Open Schematics (environ 88 000 schémas KiCad), déjà utilisé par `outils/montages_reels.py` ;
  - les projets libres d'OSHWLab (EasyEDA). KiCad sait importer EasyEDA, mais le nouveau format d'EasyEDA Pro ne passe plus (ticket KiCad n° 22239, encore ouvert d'après la page rouverte ; contournement proposé : passer par un export Altium).
- **atopile** (MIT) a un registre de modules réutilisables (packages.atopile.io, rouvert). Pas vérifié : si ses modules apportent leur placement et leur routage pour KiCad.
- **Se passer d'EasyGerber** : faire router aussi l'intérieur des blocs par Freerouting, qui est libre et déjà dans la chaîne. À essayer d'abord sur le bloc le plus simple (l'ampli), en comparant avec le routage d'EasyGerber.
- **Partager les blocs génériques** (alimentation, ESP32, ampli, tuner), pas les inventions, sous une licence libre (par exemple CERN-OHL), pour que d'autres en ajoutent. Décision de Kévin.
- Ce qui resterait non libre : les fabricants (ce sont des usines, pas des logiciels) et une partie des données des pièces (empreintes venues d'EasyEDA), que la bibliothèque officielle de KiCad remplace peu à peu (déjà les types des broches).

## Projets libres inattendus (24/10/2026, quatrième recherche)

« Rouvert » veut dire que Claude a lu la page lui-même. Rien n'est encore essayé.
- **EDeA** (rouvert : fiche NLnet, entretien NGI, articles d'AB Open et d'OSHPark, forum KiCad).
  - Ce que c'est : un catalogue et un portail communautaire de « modules de circuits éprouvés » (alimentation, conditionnement de signal, conversion, microcontrôleurs), avec un outil qui fusionne un sous-circuit, schéma et carte compris, dans un projet KiCad. Exactement notre idée de bibliothèque de blocs partagée.
  - Qui : Fully Automated OÜ (Estonie), financé par NLnet (NGI0 Discovery) d'avril 2020 à septembre 2022. Code : gitlab.com/edea-dev. Dernière version vue : 0.6.0, sur le forum KiCad, en janvier 2024.
  - Il vit encore, au ralenti (vérifié le 24/10/2026 sur GitLab et PyPI) : le paquet Python `edea` (« KiCAD file format parser and tools », licence européenne EUPL-1.2) en est à la version 0.8.4 du 09/06/2025, et le dépôt a bougé pour la dernière fois le 07/10/2025. Le groupe a aussi `edea-ms`, un serveur pour ranger les résultats de mesures de tests de cartes (à voir pour le banc de test), et `edea_draw` (KiCad vers SVG). Son portail (hub.automated.ee) refuse les robots : pas lu.
  - Le 24/10/2026, le garde-fou a refusé d'installer et de lancer `edea` dans l'espace de travail de Claude (« code venu de l'extérieur »), comme kicad-happy. À essayer sur GitHub, dans le dépôt privé de Kévin.
  - Les blocs de carte de KiCad 10 font maintenant une partie de son travail.
  - À retenir aussi : NLnet a déjà financé un outil libre de conception de cartes. Une chaîne accessible pourrait entrer dans un de ses appels (à vérifier).
- **Faire la carte au fablab, à la fraiseuse** (rouvert : deux comptes rendus de la Fab Academy 2026 ; pages des paquets Debian et Fedora de pcb2gcode).
  - Dans les fablabs, le montage habituel est une petite fraiseuse Roland SRM-20, le logiciel libre « mods » du MIT et une fraise de 1/64 de pouce (0,4 mm). pcb2gcode (GPL-3.0) fait la même chose en ligne de commande, depuis les Gerber.
  - Pour la chaîne : un fichier de règles « fraiseuse du fablab » (écarts d'environ 0,4 mm, pas de trous métallisés), pour savoir si un bloc simple peut être fait sur place, en un après-midi, avec Kévin. Les blocs actuels (écarts de 0,1 mm, prise USB-C au pas de 0,5 mm) ne passeraient pas tels quels.
  - pcb2gcode n'est pas dans les paquets d'Ubuntu 24.04 (vérifié le 24/10/2026) : il faudrait le compiler.
  - Quel fablab a une fraiseuse : l'annuaire mondial des fablabs, fablabs.io, a une interface publique (`https://api.fablabs.io/0/labs.json`, 2 885 lieux le 24/10/2026), où chaque lieu déclare ses machines. À moins de 12 km de Lyon, déclarent une fraiseuse de précision (« precision_milling », le genre de machine qui fait des cartes) : AsTech, le fablab de LyonTech-la Doua (Villeurbanne), YOUFACTORY (Villeurbanne) et l'AckLab de l'école d'architecture (Vaulx-en-Velin). La Fabrique d'Objets Libres déclare « fabrication de circuits » sur sa fiche de Saint-Priest, pas sur celle de Bron. Ce sont des déclarations, pas toujours à jour : à confirmer en leur demandant, avec la taille de leurs fraises.
- **gerber2ems** (Antmicro, Pologne ; Apache-2.0 ; rouvert). Simule une piste depuis les Gerber avec openEMS (impédance, paramètres S). Pourrait chiffrer la question 2 de la fiche (la piste FM de 1 cm). Lourd à installer. À 100 MHz, 1 cm est très court devant la longueur d'onde (environ 3 m dans l'air) : l'effet devrait être faible, mais c'est à l'électronicien de le dire.
- **Regardés, pas retenus** :
  - OrthoRoute (MIT, KiCad 10, rouvert) : l'auteur le dit lui-même, il n'est « pas un routeur général ». Il est fait pour d'énormes cartes multicouches, demande KiCad ouvert et une carte graphique NVIDIA.
  - kicad-skip (LGPL, dernière version en février 2024, KiCad 7 et plus) et kicad-sch-api (novembre 2025, KiCad 9, encore jeune), pour remplacer `sexpr.py` : pas encore. `sexpr.py` fait 60 lignes et marche.
- **À surveiller** : LibrePCB (Suisse, GPL ; version 2.0 en janvier 2026, 2.1.1 en juin 2026, rouvert). Un logiciel de conception de cartes entièrement libre et européen, avec une commande pour l'automatiser (il lui faut un écran virtuel, xvfb). Une piste pour la chaîne « toute libre », si KiCad devenait difficile à automatiser après la version 11.

## Essai : un bloc à la fraiseuse du fablab, routé par Freerouting (24/10/2026)

But : savoir si un bloc peut être fait à la fraiseuse d'un fablab, et si un outil libre (Freerouting) peut router l'intérieur d'un bloc à la place d'EasyGerber.
- **Comment** :
  - carte `cartes/essai-ampli-fraiseuse.json` : le seul bloc ampli, avec le placement d'EasyGerber ;
  - règles `bibliotheque/regles/fraiseuse-fablab.json` (hypothèses de Claude, à confirmer avec le fablab) : 0,4 mm au moins entre deux cuivres et pour une piste, pistes de 0,5 mm, vias de 1,8 mm pour un trou de 0,8 mm où l'on soude un fil, 0,5 mm du bord. La commande « Autres fabricants » ne les lit pas (type « fablab ») ;
  - `outils/vider_routage.py` enlève le routage d'EasyGerber et ajoute une bande de garde le long du bord ; avec « une-face », il interdit le dessous et les vias.

  ```
  python3 scripts/assembler.py cartes/essai-ampli-fraiseuse.json resultats/essai-ampli-fraiseuse
  python3 outils/vider_routage.py resultats/essai-ampli-fraiseuse/carte.kicad_pcb 0.6
  python3 scripts/freerouter.py cartes/essai-ampli-fraiseuse.json resultats/essai-ampli-fraiseuse/carte.kicad_pcb OUTILS/freerouting-2.1.0.jar
  ```
- **Résultats** :
  - le routage d'EasyGerber, tel quel, sous les règles de fraiseuse : 79 erreurs (pistes de 0,25 mm, 14 vias de 0,5 mm, écarts trop petits). Il ne passe pas ;
  - Freerouting, sur deux faces, en une vingtaine de secondes : 2 essais sur 3 complets, sans aucune erreur pour KiCad, avec 11 vias chacun (11 fils à souder à la main). Le troisième laisse 2 liaisons. Freerouting ne donne jamais deux fois le même résultat : on garde un essai complet ;
  - sur une seule face, sans via : 6 liaisons manquent encore après 3 passages. Il faudrait 2 ou 3 fils volants (des « straps »), ou un placement plus aéré ;
  - sans la bande de garde, Freerouting passe à moins de 0,5 mm du bord (5 erreurs) : il ne connaît pas cette règle ;
  - l'essai complet est rangé dans `resultats/essai-ampli-fraiseuse/` : la carte KiCad, et une image des deux faces pour les gens du fablab.
- **Ce que ça montre** : on peut garder le placement d'EasyGerber et faire router l'intérieur d'un bloc par un outil libre. Pour une carte fraisée, il faudra un placement plus aéré, pour avoir moins de vias.
- **Pas vérifié** : les vraies règles de la fraiseuse (taille des fraises, une ou deux faces), et le fraisage lui-même. Pour essayer le bloc seul sur place, il lui manque une pastille de masse au bord.

## Veille

Une tâche programmée, « Veille chaîne puzzle », tourne le 1er de chaque mois à 8 h 41 (heure de Paris), depuis le 23/10/2026. Elle compare aux références de cette version : versions des logiciels (KiCad 11 et le retrait de SWIG en premier), règles de JLCPCB, PCBWay et AISLER, stock des pièces clés, pistes à revérifier. Elle cherche aussi du nouveau, avec la règle des deux sources. Elle envoie un rapport daté et peut proposer une mise à jour de la compétence, que Kévin relit avant de l'enregistrer. Elle n'a pas les fichiers de la chaîne : elle dit quoi changer et où, et les changements se font ici, avec une entrée d'historique.

## Outils regardés, pas retenus pour l'instant (22/10/2026)

- **atopile** (libre) : décrit le circuit avec des modules réutilisables pris dans un catalogue, et met à jour le fichier KiCad. C'est le plus proche de l'idée des briques, pour le schéma. Il se dit lui-même en pré-version et en plein développement, et le placement et le routage se font toujours dans KiCad. À revoir quand il sera stable.
- **tscircuit** (libre) : des circuits écrits comme des composants de code. Son routeur est encore en développement, et il ne place pas les composants tout seul. Trop jeune.

## Notes pour le logiciel de RADIONÉO

Broches de l'ESP32-S3 dans la version 3 de la carte. Elles ont été choisies pour le routage, et aucun logiciel n'existait encore.

- I2C SDA : IO10 (broche 18)
- I2C SCL : IO11 (broche 19)
- Reset du tuner : IO12 (broche 20)
- Interruption du tuner : IO13 (broche 21)
- Coupure de l'ampli (AMP_MUTE) : IO9 (broche 17)
- USB : IO19 et IO20 ; molette : IO4, IO5 et IO6 ; mesure audio : IO1 ; LED : IO48

Ce que dit la fiche du tuner Si4735 pour le logiciel :
- Au démarrage, le mode I2C est choisi tout seul par des résistances internes. Il faut laisser la broche RADIO_INT en entrée pendant le reset du tuner.
- SCL doit être à l'état haut au moment du reset : la résistance de tirage s'en charge.
- Adresse I2C : la broche SEN est à la masse ; l'adresse correspondante est dans la note AN332.

Carte v4, tuner Si4732-A10 : sa fiche publique ne fait que 3 pages. On applique les mêmes règles que pour le Si4735, de la même famille : au reset, GPO2/INT est tiré vers 0 et GPO1 vers 1 par des résistances internes de 1 MΩ, et SCL doit être à 1. La broche SENB est à la masse : adresse 0x11. Les broches GPO1 et NC ne sont pas reliées.

Ampli PAM8403 : SHDN est relié au 5 V, donc l'ampli est allumé. MUTE est actif à l'état bas, avec R7 vers la masse : l'ampli reste muet tant que l'ESP32 ne met pas AMP_MUTE à l'état haut.

## À vérifier avant de commander

- **Le tuner.** Le Si4735 n'est plus en stock chez JLCPCB (constaté le 23/10/2026). Kévin a choisi le Si4732-A10 : c'est la carte radio v4. La v3 ne peut plus être assemblée par JLCPCB telle quelle. Sur la v4, ce qui n'est pas vérifié : le montage autour du Si4732 (quartz, découplage) reprend celui du Si4735, faute de schéma d'application dans sa fiche courte. Le premier prototype le dira.
- **Les trous de fixation** : ajoutés le 23/10/2026, tous en haut de la carte (il n'y avait pas de place ailleurs). Le trou du coin en haut à gauche est à environ 6 mm de la zone de l'antenne : question 10 pour l'électronicien.
- **Le régulateur 3,3 V** : mesurer le vrai courant au test. Au-delà d'environ 0,33 A, il chauffe trop : il faudra un régulateur à découpage.

- L'impédance d'entrée de l'ampli PAM8403. Le tuner demande au moins 10 kΩ de charge sur sa sortie LOUT. La simulation donne 14 kΩ si l'ampli fait 20 kΩ (bon), et 8,3 kΩ s'il fait 10 kΩ (trop faible). La fiche téléchargée ne donne pas ce chiffre.
- **Les condensateurs sur VBUS** : environ 33 µF, pour 10 µF au plus selon la règle de l'USB 2.0 (charge prise au branchement). Question 11 de la fiche.
- **Les lignes USB D+ et D-** : pas d'emplacement pour les résistances en série (22 ou 33 Ω) que recommande le guide d'Espressif. Question 12 de la fiche.

## Historique

- **1.28 — 24/10/2026** : essai du bloc ampli à la fraiseuse du fablab, routé par Freerouting (règles `fraiseuse-fablab.json`, `outils/vider_routage.py`, carte `essai-ampli-fraiseuse.json`) : complet sur deux faces, sans erreur, avec 11 vias ; pas sur une seule face.
- **1.27 — 24/10/2026** : fablabs autour de Lyon qui déclarent une fraiseuse de précision, d'après l'interface publique de fablabs.io ; état d'EDeA (vivant, au ralenti ; licence EUPL) ; le garde-fou refuse aussi de lancer EDeA dans l'espace de travail de Claude ; pcb2gcode absent d'Ubuntu 24.04.
- **1.26 — 24/10/2026** : quatrième recherche, « Projets libres inattendus » : EDeA (bibliothèque partagée de sous-circuits KiCad, financée par NLnet), fraisage des cartes au fablab (mods, pcb2gcode), gerber2ems ; OrthoRoute, kicad-skip et kicad-sch-api regardés, pas retenus ; LibrePCB à surveiller.
- **1.25 — 24/10/2026** : pistes pour une bibliothèque de blocs plus rapide et une chaîne toute libre (blocs de carte de KiCad 10, montages publiés, atopile, Freerouting à la place d'EasyGerber, partage des blocs génériques). Rien n'est encore essayé.
- **1.24 — 24/10/2026** : la chaîne est prête pour un dépôt GitHub privé (`README.md`, et un `.gitignore` qui laisse de côté les modèles 3D refaits par la chaîne et les schémas d'autres projets) ; kicad-happy y tournera à chaque envoi (`.github/workflows/kicad-happy.yml`). Le dépôt reste à créer par Kévin. La suite pour la radio v4 : la relecture par un électronicien.
- **1.23 — 24/10/2026** : le contrôle du circuit voit maintenant tout seul les deux points trouvés à la main : plus de 10 µF sur le VBUS d'une prise USB, et une ligne de données USB sans résistance en série (règles 10 et 11 de `controle_circuit.py`, essayées sur une copie corrigée de la radio v4).
- **1.22 — 24/10/2026** : contrôles de kicad-happy refaits à la main sur la radio v4, car l'outil n'a pas pu être lancé ici ; fiche de questions de la radio v4 en version 1.5, avec deux questions de plus (condensateurs sur VBUS, lignes USB) ; dossier de relecture refait (12 questions).
- **1.21 — 24/10/2026** : contrôle du circuit (`controle_circuit.py`, étape 0 quater) ; vrais types de broches depuis la bibliothèque officielle de KiCad (`outils/typer_broches.py`, `types-broches.json`), drapeaux d'alimentation, étiquettes globales et ERC complet dans `schema.py` ; parité schéma ↔ carte de KiCad ; correction des champs des empreintes (18 références LCSC fausses dans le fichier KiCad) ; essai par erreurs volontaires. La chaîne relit ses scripts avant de partir (`relire_scripts.py`, pyflakes) et signale toute étape plantée (code de sortie 2) ; la maquette, qui plantait depuis la version 1.16, est corrigée. Composants rouverts : kicad-happy, KiPart, akcli, KiBot, KiPilot.
- **1.20 — 24/10/2026** : dossier de relecture pour un électronicien (`dossier_relecture.py`, étape 7), avec des PDF balisés ; constat sur les 130 avertissements du contrôle électrique ; première demande préparée pour ECTI.
- **1.19 — 23/10/2026** : plan à toucher sur papier gonflé (`plan_tactile.py`, étape 0 ter de la commande, règles dans `plan_tactile.json`), essayé sur la radio v4 (PDF, pas encore imprimé).
- **1.18 — 23/10/2026** : troisième recherche, « Pistes trouvées partout ». Rester sur KiCad 10.0.x tant que kicad-python et KiKit ne marchent pas sans fenêtre. Pistes : tests automatiques (pytest-embedded, Wokwi, esp-emulator), afficheurs tactiles, papier thermogonflé, RUDO, brevets, Vision Participative à Lyon (30/11/2026), Fabrique d'Objets Libres, fil KiCad sur l'accessibilité, aide de la Région.
- **1.17 — 23/10/2026** :
  - deuxième recherche, « Pistes trouvées ailleurs » : braille en bosses de soudure, Stencilframer, lxi-tools, alimentation pilotable, souder sans la vue, UNARAF ;
  - veille mensuelle de la chaîne (tâche programmée) ;
  - compétence `carte-puzzle` mise au niveau de la méthode (elle en était à la 1.11), avec une section sur la veille.
- **1.16 — 23/10/2026** :
  - banc de test : nom du signal en lettres en relief sous chaque numéro ; braille par liblouis, et désactivable ; la maquette passe aussi par liblouis (mêmes points, vérifié sur tous ses textes) ;
  - étape 13 : `broches_esp32.py`, programme d'essai de la radio v4 (compilé), mesures guidées avec sigrok ;
  - boîtier : étiquettes en braille à embosser (`etiquettes-braille.txt`, pour AccessBrailleRAP) ;
  - pistes trouvées dans des coins peu connus.
- **1.15 — 23/10/2026** :
  - trous de fixation (« trous_fixation » dans la carte) : M3 métallisés reliés à la masse, placés hors des blocs, des zones sans cuivre et des couloirs entre blocs ; « sur la carte seulement » pour le schéma et les listes. Radio v4 : 4 trous, carte agrandie de 7 mm en haut (80 × 73 mm), toute la chaîne repassée ;
  - banc de test à pointes (étape 12, `banc_test.py`) : carte du banc, socle, porte-pointes, capot avec entonnoirs, braille et chiffres en relief, 13 contrôles ;
  - boîtier : tétons dans les trous de fixation, plots qui pincent aux coins sans trou ;
  - `modeles3d.py`, partagé par le boîtier et le banc ; SciPy dans `installer-ubuntu.sh`.
- **1.14 — 23/10/2026** : boîtier d'essai (étape 11, `boitier.py`, YAPP_Box et OpenSCAD), avec ouvertures, boutons imprimés, noms en creux, plots de maintien et 17 contrôles ; ouvertures, boutons et fils déclarés dans `bloc.json` ; OpenSCAD, YAPP_Box (version épinglée), trimesh et matplotlib dans `installer-ubuntu.sh`.
- **1.13 — 23/10/2026** : hackaday.io devient une source de premier rang ; règle des deux sources indépendantes ; deux pistes pour ce que la chaîne ne sait pas faire, le boîtier (YAPP_Box, essayé sur la radio v4) et le banc de test à pointes. Constat : la radio v4 n'a pas de trous de fixation.
- **1.12 — 23/10/2026** : recherche de projets proches sur hackaday.io (Firecrawl) ; la radio Fennec, très proche de la radio v4, est reprise dans la fiche de questions et le plan de test.
- **1.11 — 23/10/2026** :
  - autres fabricants (étape 3 quater, `fabricants.py`) : PCBWay et AISLER, en plus de JLCPCB ;
  - fiche de questions pour l'électronicien, et niveaux de confiance d'une carte ;
  - le schéma porte le fabricant et la référence de chaque pièce ; les sorties en cuivre nu sont hors liste des pièces et placement, dans le schéma et sur la carte ;
  - contrôle indépendant : distance au bord mesurée sur le vrai contour ;
  - `outils/montages_reels.py` : montages publiés d'une puce (jeu Open Schematics), repris dans la fiche de questions de la radio v4 (version 1.1).
- **1.10 — 23/10/2026** : maquette en couleurs (une couleur et une texture par bloc, noms en lettres en relief), en une pièce (3MF) ou en puzzle (une pièce par bloc, posée sur une pente à 45°), avec une notice pour la personne qui imprime.
- **1.9 — 23/10/2026** : carte radio v4 avec un nouveau bloc tuner, `B_tuner_si4732` (Si4732-A10 en SOIC-16, prise d'antenne SMA à 0,53 $), routé par EasyGerber et ajouté à la bibliothèque sans toucher l'ancien. La v4 passe tous les contrôles : disposition, KiCad sans erreur, 35 réseaux sur 35, contrôle indépendant « rien à corriger », schéma identique à la carte, 24 pièces sur 24 en stock pour 5 cartes. Freerouting a eu besoin de 3 passages pour le 3,3 V. Plan de test `cartes/radio-v4-plan-de-test.md` (version 2.0).
- **1.8 — 23/10/2026** : bilan d'échauffement (étape 0 bis) et vérification des stocks chez JLCPCB (option `--disponibilite`). Constat : le tuner Si4735 manque chez JLCPCB.
- **1.7 — 23/10/2026** :
  - schéma KiCad produit par la chaîne (étape 9 bis), contrôlé par KiCad et comparé à la carte ;
  - prise USB-C corrigée (pastilles de masse raccourcies de 0,02 mm, décision de Kévin) : la carte radio v3 passe tous les contrôles ;
  - jusqu'à 3 passages de Freerouting, et les vias qui ne mènent nulle part sont enlevés ;
  - plan de test de la carte radio à la réception (`cartes/radio-v3-plan-de-test.md`).
- **1.6 — 23/10/2026** :
  - contrôle de la disposition avant le routage (`disposition.py`, étape 0) ;
  - recette Docker essayée de bout en bout ;
  - vias de 0,7 mm, et règle JLCPCB des trous métallisés écrite pour KiCad (`carte.kicad_dru`).
  - Les deux cartes d'essai passent tous les contrôles, sauf la prise USB-C.
- **1.5 — 22/10/2026** : la maquette à toucher (étape 10), la recette d'installation (Ubuntu et Docker), et la compétence Claude « carte-puzzle ».
- **1.4 — 22/10/2026** : la chaîne devient un assemblage de briques.
  - Plus aucun nom de carte ni de bloc dans le code : une bibliothèque de blocs, un fichier de règles par fabricant, un fichier par carte.
  - Les blocs peuvent être tournés.
  - Deuxième passage de Freerouting, à la largeur minimale, si une alimentation n'est pas reliée.
  - La largeur des alimentations passe par les classes de KiCad, au lieu d'une retouche à la main du fichier pour Freerouting.
  - Le contrôle indépendant finit par un bilan.
  - Fiche `POUR-LE-FABLAB.md` pour trouver de l'aide.
- **1.3 — 22/10/2026** : la chaîne passe sur KiCad 10 et tient en une commande (`chaine.py`). Les vraies empreintes sont posées dès l'assemblage. `import_ses.py` est retiré : KiCad 10 reprend lui-même le travail de Freerouting.
- **1.2 — 22/10/2026** : KiCad 10 et KiKit installés et essayés. Les règles JLCPCB sont écrites dans le projet. Image 3D de la carte.
- **1.1 — 22/10/2026** : ajout d'easyeda2kicad (vraies empreintes, modèles 3D, contrôle des empreintes et du brochage USB-C) et de ngspice (simulation des sorties audio). KiCad 10 et KiKit sont bloqués en attente d'accord.
- **1.0 — 22/10/2026** : première version de la chaîne, à partir de la carte radio RADIONÉO v3 (80 × 66 mm, 43 composants).
  - 3 blocs EasyGerber avec 19 sorties ;
  - liaisons tracées par Freerouting ;
  - contrôles KiCad et Gerber passés.
  - Le bloc tuner est tourné d'un demi-tour pour que la prise d'antenne sorte par le bord.
