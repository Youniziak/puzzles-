# Relecture de la carte « RADIONÉO carte radio v4 »

Kévin Chatellard — Exylia Project — 24/10/2026

Je conçois sans la vue une radio de table, RADIONÉO, prévue en matériel libre. Cette carte en est le cœur : alimentation par USB-C, microcontrôleur ESP32-S3, tuner FM et AM Si4732, ampli PAM8403.

## Ce que je vous demande

Répondre aux 12 questions de la fiche (01-questions.pdf) : elles portent sur ce que les outils automatiques ne savent pas juger. Pas besoin de tout relire : le reste est déjà vérifié (voir plus bas). Temps estimé : une à deux heures.

Vous pouvez répondre comme vous préférez : dans la fiche (en PDF annoté, ou dans le fichier texte 01-questions.md), par courriel, ou de vive voix. Une réponse partielle m'aide déjà beaucoup.

## La carte en bref

- 80 × 73 mm, 2 couches, prévue pour : JLCPCB, 2 couches, cuivre 35 µm.
- 43 composants, en 3 blocs :
  - alim : Alimentation USB-C (protection USBLC6, régulateur AMS1117 3,3 V), ESP32-S3-WROOM-1, boutons RESET et BOOT, LED, prise de la molette.
  - tuner : Tuner AM/FM/ondes courtes Si4732-A10 (SOIC-16) avec son quartz et la prise d'antenne SMA coudée BWSMA-KWE-Z001, qui sort par la droite. Remplace B_tuner (Si4735, en rupture de stock le 23/10/2026). Adresse I2C 0x11 (SENB à la masse).
  - ampli : Ampli stéréo PAM8403 (2 × 3 W), avec ses condensateurs et les prises des haut-parleurs.
- Niveau de confiance de la carte aujourd'hui : contrôlée par la chaîne. Pas encore relue par un électronicien, pas encore essayée sur prototype.

## Comment elle a été faite

Chaque bloc a été routé par EasyGerber, puis les blocs ont été assemblés et contrôlés avec des logiciels libres : KiCad 10, Freerouting et KiKit, plus un contrôle indépendant des fichiers Gerber. Je conçois mes cartes sans la vue : un regard humain du métier est l'étape qui manque.

## Ce qui est déjà vérifié (inutile d'y passer du temps)

- Toutes les liaisons sont tracées (35 réseaux sur 35), sans court-circuit ; le schéma et la carte sont identiques, liaison par liaison.
- Les règles de fabrication de JLCPCB : écarts, perçages, bord, couronnes, et un contrôle indépendant relu sur les fichiers Gerber.
- La largeur des pistes d'alimentation pour le courant demandé (IPC-2221, +10 °C).
- Rien dans la zone de l'antenne de l'ESP32.
- Le stock des 24 pièces chez JLCPCB pour 5 cartes (le 23/10/2026).
- L'échauffement du régulateur et de l'ampli, calculé avec les chiffres des fiches.
- Le contrôle électrique du schéma par KiCad, avec le rôle de chaque broche pris dans la bibliothèque officielle de KiCad : aucune erreur, aucun avertissement.
- Les erreurs bêtes : broches de masse et d'alimentation, SDA et SCL, sens du régulateur, condensateur de découplage à moins de 5 mm de chaque alimentation de puce, résistances de tirage I2C.

## Le contrôle électrique

Le contrôle électrique de KiCad (ERC) trouve 0 erreur(s) et 0 avertissement(s). Les broches des puces ont le type de la bibliothèque officielle de KiCad (entrée, sortie, alimentation…), ce qui permet à ce contrôle de voir une sortie contre une sortie ou une alimentation non fournie.

## Les fichiers du dossier

- 01-questions.pdf : la fiche de questions (12 questions), en PDF.
- 02-schema.pdf : le schéma (KiCad).
- 03-carte-couches.pdf : la carte, une couche par page : cuivre dessus, cuivre dessous, sérigraphie dessus et dessous, avec le contour.
- 04-carte-3d.png : la carte en 3D, vue de dessus.
- 05-plan-de-test.pdf : le plan de test à la réception de la carte, en PDF.
- 06-controles.txt : les bilans des contrôles automatiques de la chaîne.
- kicad/ : le projet KiCad 10 à ouvrir (carte.kicad_pro) : carte, schéma, règles, empreintes et symboles ; sans les modèles 3D, trop lourds.
- fabrication/gerbers.zip : les fichiers Gerber et de perçage.
- fabrication/BOM-JLCPCB.csv : la liste des pièces (numéros LCSC).
- fabrication/CPL-JLCPCB.csv : le placement des pièces.
- 01-questions.md : la fiche de questions, en texte (pour y écrire les réponses).
- 05-plan-de-test.md : le plan de test, en texte.

Merci d'avance pour votre temps.
