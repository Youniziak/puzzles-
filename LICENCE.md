# Licences de la chaîne « puzzle »

Exylia Project — Kévin Chatellard — 25 octobre 2026

La chaîne est libre, sous des licences strictes (dites « réciproques ») : on peut l'utiliser, l'étudier, la modifier et la partager ; mais une version modifiée qu'on diffuse doit rester libre, sous la même licence. Personne ne peut donc la reprendre pour en faire une version fermée.

Copyright © 2026 Kévin Chatellard — Exylia Project, sauf mention contraire plus bas.

## Quelle licence pour quoi

- **Le logiciel : GNU AGPL-3.0, ou une version plus récente** (texte : `LICENSES/AGPL-3.0-or-later.txt`).
  - Ce que ça couvre : les scripts (`scripts/`, `outils/`), les réglages GitHub (`.github/`), l'installation (`installer-ubuntu.sh`, `Dockerfile`, `.dockerignore`, `.gitignore`), le programme d'essai de la radio (`cartes/radio-v4-essai/`), les règles et les données de la chaîne (`bibliotheque/regles/`, `bibliotheque/controles-verifies.json`, `bibliotheque/empreintes/correspondance.json`, `bibliotheque/empreintes/retouches.json`, `bibliotheque/empreintes/attendu.json`).
  - Elle vaut aussi pour un service en ligne : qui propose une version modifiée de la chaîne sur un site doit en donner le code.
- **Le matériel : CERN-OHL-S-2.0** (texte : `LICENSES/CERN-OHL-S-2.0.txt`).
  - Ce que ça couvre : les descriptions de cartes (`cartes/*.json`), les blocs (`bibliotheque/blocs/*/bloc.json`, `bibliotheque/blocs-libres/`), et ce que la chaîne produit pour fabriquer ou toucher une carte (`resultats/` : cartes KiCad, Gerber, maquettes, boîtiers, bancs de test, plans en papier gonflé).
- **Les textes : CC BY-SA 4.0** (texte : `LICENSES/CC-BY-SA-4.0.txt`).
  - Ce que ça couvre : la méthode, les fiches, le guide pour le fablab, ce fichier (tous les `.md`).

Le fichier `REUSE.toml` dit la même chose pour les programmes, selon la spécification REUSE de la FSFE (Free Software Foundation Europe).

## Ce qui vient d'ailleurs, et garde sa licence

- `bibliotheque/blocs-libres/alim_decoupage_olimex/` : tiré d'une carte d'OLIMEX Ltd, sous CERN-OHL-S-2.0 ; origine et modifications dans son `LICENCE.txt`. Une carte qui reprend ce bloc garde la mention d'Olimex (par exemple `resultats/essai-radio-v4-decoupage/`).
- `bibliotheque/empreintes/types-broches.json` et `bibliotheque/empreintes/symboles-officiels.json` : tirés de la bibliothèque officielle de KiCad (CC BY-SA 4.0, avec son exception pour les cartes).
- Les empreintes, symboles et modèles 3D de LCSC et EasyEDA (`radioneo.pretty/`, `radioneo.kicad_sym`, `radioneo.3dshapes/`) **ne sont pas dans le dépôt**, ni dans son historique : les conditions d'utilisation d'EasyEDA interdisent de republier leur contenu (lues le 25/10/2026 : https://easyeda.com/page/legal). Chacun les télécharge chez soi, pour son usage, avec `outils/telecharger_bibliotheque.py` (par easyeda2kicad). Le dépôt ne garde que la liste des pièces (`correspondance.json`), les retouches de la chaîne (`retouches.json`) et des sommes de contrôle (`attendu.json`). Les cartes KiCad de `resultats/` contiennent encore une copie des empreintes qu'elles utilisent, comme toute carte KiCad : c'est une zone plus grise, à régler en passant peu à peu aux empreintes officielles de KiCad.
- `bibliotheque/blocs/*/easygerber/` : fichiers produits par le service EasyGerber. Ses conditions (lues le 25/10/2026 : https://www.easygerber.com/terms) disent que l'utilisateur garde ses droits sur ce qu'il crée ; les pièces et modèles d'autres fournisseurs restent sous leurs propres conditions.
- `resultats/*/montages-reels/` et les rapports de `outils/chercher_fonction.py` : des résumés tirés de jeux de données publics (Ohmatic et Open Schematics, CC BY 4.0 ; kicad9plus ; Electronics Stack Exchange, CC BY-SA ; liste et licences dans `outils/jeux_donnees.py`). On y lit et on cite : liaisons, valeurs, descriptions courtes des dépôts, débuts de questions et de réponses, toujours avec le lien de la source. Chaque projet cité garde sa propre licence. Les schémas des autres projets ne sont pas dans le dépôt (ils vont dans un dossier `schemas/` que Git ignore), ni les jeux eux-mêmes (ils vont dans un cache, chez soi). Un extrait d'Electronics Stack Exchange garde sa licence CC BY-SA, et ses auteurs sont nommés sur la page de la question.
- Jeux regardés et pas utilisés pour leurs données : mascarade (surtout écrit par une IA) ; kicad-netlist-sft ne sert que d'index, car ses liaisons sont fausses dans des cas vérifiés (détail dans `outils/jeux_donnees.py`).
- Les logiciels dont la chaîne se sert (KiCad, Freerouting, KiKit, kicad-happy, EDeA…) gardent chacun leur licence. Ils ne sont pas dans le dépôt.

## Pourquoi des licences strictes

Avec une licence trop souple, une entreprise pourrait reprendre la chaîne, la fermer et ne rien rendre. Avec une licence réciproque, une amélioration diffusée revient à tout le monde.

## Une autre licence ?

L'auteur peut proposer ses propres parties sous une autre licence, par exemple à une entreprise qui ne veut pas publier ses changements. Les parties venues d'ailleurs restent sous leur licence. À décider avant la première contribution d'une autre personne : lui demander si sa contribution pourra aussi être proposée sous une autre licence.

Ce fichier n'est pas un avis juridique. Le dépôt est public depuis le 25/10/2026 ; une relecture par un juriste reste la bienvenue.
