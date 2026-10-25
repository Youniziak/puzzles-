# Chaîne « puzzle » — Exylia Project

Concevoir des cartes électroniques sans la vue : la carte est découpée en blocs par fonction, chaque bloc est routé par EasyGerber, puis la chaîne recolle et vérifie le tout avec des logiciels maintenus (KiCad 10, Freerouting, KiKit…). Elle produit aussi de quoi toucher la carte avant de la commander : plan sur papier gonflé, maquette, boîtier et banc de test à imprimer en 3D.

Dépôt privé. La première carte faite avec la chaîne est la radio RADIONÉO v4.

- `METHODE-CARTES-PUZZLE.md` : la méthode, ce qui a été appris, et l'historique des versions.
- `POUR-LE-FABLAB.md` : les briques et la colle, pour quelqu'un qui voudrait aider.
- `SKILL-carte-puzzle.md` : la compétence Claude qui sait se servir de la chaîne.
- `installer-ubuntu.sh` et `Dockerfile` : pour installer les logiciels.
- `scripts/chaine.py` : la chaîne en une commande.
- `.github/workflows/kicad-happy.yml` : un deuxième avis sur chaque carte, par l'outil libre kicad-happy, à chaque changement.
- `.github/workflows/edea.yml` : un essai de l'outil libre EDeA (bibliothèque partagée de blocs KiCad) : sait-il lire nos fichiers ?

Ne sont pas dans le dépôt : les modèles 3D à imprimer (refaits par la chaîne), et les schémas d'autres projets publiés.

## Licences

Libres et strictes : le logiciel sous GNU AGPL-3.0 (ou plus récente), le matériel (cartes, blocs, maquettes) sous CERN-OHL-S-2.0, les textes sous CC BY-SA 4.0. Le détail, et ce qui vient d'ailleurs : `LICENCE.md`. Les textes des licences : `LICENSES/`.
