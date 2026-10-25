# Licences de la chaîne « puzzle »

Exylia Project — Kévin Chatellard — 25 octobre 2026

La chaîne est libre, sous des licences strictes (dites « réciproques ») : on peut l'utiliser, l'étudier, la modifier et la partager ; mais une version modifiée qu'on diffuse doit rester libre, sous la même licence. Personne ne peut donc la reprendre pour en faire une version fermée.

Copyright © 2026 Kévin Chatellard — Exylia Project, sauf mention contraire plus bas.

## Quelle licence pour quoi

- **Le logiciel : GNU AGPL-3.0, ou une version plus récente** (texte : `LICENSES/AGPL-3.0-or-later.txt`).
  - Ce que ça couvre : les scripts (`scripts/`, `outils/`), les réglages GitHub (`.github/`), l'installation (`installer-ubuntu.sh`, `Dockerfile`, `.dockerignore`, `.gitignore`), le programme d'essai de la radio (`cartes/radio-v4-essai/`), les règles et les données de la chaîne (`bibliotheque/regles/`, `bibliotheque/controles-verifies.json`, `bibliotheque/empreintes/correspondance.json`).
  - Elle vaut aussi pour un service en ligne : qui propose une version modifiée de la chaîne sur un site doit en donner le code.
- **Le matériel : CERN-OHL-S-2.0** (texte : `LICENSES/CERN-OHL-S-2.0.txt`).
  - Ce que ça couvre : les descriptions de cartes (`cartes/*.json`), les blocs (`bibliotheque/blocs/*/bloc.json`, `bibliotheque/blocs-libres/`), et ce que la chaîne produit pour fabriquer ou toucher une carte (`resultats/` : cartes KiCad, Gerber, maquettes, boîtiers, bancs de test, plans en papier gonflé).
- **Les textes : CC BY-SA 4.0** (texte : `LICENSES/CC-BY-SA-4.0.txt`).
  - Ce que ça couvre : la méthode, les fiches, le guide pour le fablab, ce fichier (tous les `.md`).

Le fichier `REUSE.toml` dit la même chose pour les programmes, selon la spécification REUSE de la FSFE (Free Software Foundation Europe).

## Ce qui vient d'ailleurs, et garde sa licence

- `bibliotheque/blocs-libres/alim_decoupage_olimex/` : tiré d'une carte d'OLIMEX Ltd, sous CERN-OHL-S-2.0 ; origine et modifications dans son `LICENCE.txt`. Une carte qui reprend ce bloc garde la mention d'Olimex (par exemple `resultats/essai-radio-v4-decoupage/`).
- `bibliotheque/empreintes/types-broches.json` et `bibliotheque/empreintes/symboles-officiels.json` : tirés de la bibliothèque officielle de KiCad (CC BY-SA 4.0, avec son exception pour les cartes).
- `bibliotheque/empreintes/radioneo.pretty/`, `radioneo.kicad_sym` et `radioneo.3dshapes/` : empreintes, symboles et modèles 3D téléchargés depuis la bibliothèque de LCSC et EasyEDA, par easyeda2kicad. Leurs conditions sont à vérifier avant de publier.
- `bibliotheque/blocs/*/easygerber/` : fichiers produits par le service EasyGerber. Ses conditions sont à vérifier avant de publier.
- `resultats/*/montages-reels/` : des résumés tirés du jeu de données Open Schematics (Hugging Face, CC BY 4.0). Les schémas des autres projets ne sont pas dans le dépôt.
- Les logiciels dont la chaîne se sert (KiCad, Freerouting, KiKit, kicad-happy, EDeA…) gardent chacun leur licence. Ils ne sont pas dans le dépôt.

## Pourquoi des licences strictes

Avec une licence trop souple, une entreprise pourrait reprendre la chaîne, la fermer et ne rien rendre. Avec une licence réciproque, une amélioration diffusée revient à tout le monde.

## Une autre licence ?

L'auteur peut proposer ses propres parties sous une autre licence, par exemple à une entreprise qui ne veut pas publier ses changements. Les parties venues d'ailleurs restent sous leur licence. À décider avant la première contribution d'une autre personne : lui demander si sa contribution pourra aussi être proposée sous une autre licence.

Ce fichier n'est pas un avis juridique : à faire relire avant de publier le dépôt.
