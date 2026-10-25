# Carte radio RADIONÉO v4 — questions pour un électronicien

Exylia Project — version 1.8 — 25 octobre 2026

Je conçois mes cartes sans la vue, avec une chaîne d'outils qui contrôle tout ce qu'un programme peut contrôler. Il reste des choix qu'il faut un humain du métier pour juger. Cette fiche les liste en questions précises : pas besoin de tout relire.

**Niveau de confiance de la carte aujourd'hui : contrôlée par la chaîne.** Pas encore relue par un électronicien, pas encore essayée sur prototype.

## À apporter

- La maquette à toucher (en couleurs : alimentation et ESP32 en bleu, tuner en orange, ampli en vert).
- Le schéma : `resultats/radio-v4/schema.pdf`.
- Le plan de test : `cartes/radio-v4-plan-de-test.md`.
- Cette fiche, pour noter les réponses.

## Ce que la chaîne a déjà vérifié (inutile d'y passer du temps)

- Toutes les liaisons sont tracées (35 réseaux sur 35), sans court-circuit ; le schéma et la carte sont identiques, liaison par liaison.
- Les règles de fabrication de JLCPCB : écarts, perçages, bord, couronnes, et un contrôle indépendant relu sur les fichiers Gerber.
- La largeur des pistes d'alimentation pour le courant demandé (IPC-2221, +10 °C).
- Rien dans la zone de l'antenne de l'ESP32.
- Le stock des 24 pièces chez JLCPCB pour 5 cartes (le 23/10/2026).
- L'échauffement du régulateur et de l'ampli, calculé avec les chiffres des fiches.
- Le contrôle électrique du schéma par KiCad, avec le rôle de chaque broche pris dans la bibliothèque officielle de KiCad : aucune erreur, aucun avertissement.
- Les erreurs bêtes : broches de masse et d'alimentation, SDA et SCL, sens du régulateur, condensateur de découplage à moins de 5 mm de chaque alimentation de puce, résistances de tirage I2C.
- Un deuxième avis automatique, par l'outil libre kicad-happy (version 2.3.2), le 25/10/2026 : aucune erreur sur le schéma, et rien qui contredise la chaîne. Il est moins strict qu'elle sur l'USB (il accepte les 33 µF sur VBUS, et ne cherche pas de résistances en série sur D+ et D-) : les questions 11 et 12 restent. Ses deux remarques utiles sont reprises aux questions 2 et 5.

## Les questions

### 1. Le montage du tuner Si4732-A10
Le montage est repris de celui du Si4735, de la même famille, car la fiche du Si4732 ne fait que 3 pages, sans schéma d'application : quartz de 32,768 kHz entre RCLK et GPO3/DCLK avec deux 22 pF à la masse ; 100 nF près de VDD et 10 µF à l'entrée du 3,3 V ; 1 nF en série vers FMI ; 470 nF en série vers AMI ; RFGND et SENB à la masse ; GPO1 et NC non reliés.
**Est-ce correct pour le Si4732-A10 ?**

Ce que montrent des montages publiés (jeu Open Schematics, 4 projets avec un Si4732-A10, détail dans `resultats/radio-v4/montages-reels/montages.txt`) :
- deux versions de la radio `ralphxavier/SI4735`, dont une avec un ESP32-S3 comme la nôtre, ont **le même montage** : quartz de 32,768 kHz avec deux 22 pF, 1 nF vers FMI, 470 nF vers AMI, 100 nF sur VDD, GPO1, GPO2 et NC non reliés ;
- `bt-soft/pico-radio-5` a aussi le quartz et les deux 22 pF, mais filtre l'alimentation du tuner (inductance de 220 µH, puis 4,7 µF et 100 nF), et met 33 pF et une inductance de 220 µH sur FMI, 1 nF sur AMI.

- sur hackaday.io, la radio Fennec (hackaday.io/project/206572, CiferTech, licence MIT : ESP32-S3 + Si4732-A10 + PAM8403, comme la nôtre) a aussi le quartz avec deux 22 pF et 100 nF sur VDD ; mais sa broche SENB est au 3,3 V (adresse I2C 0x63 au lieu de 0x11), et une seule prise SMA sert à la FM et à l'AM, à travers des condensateurs de 100 nF et des inductances de 10 mH.

**Concordance** : le quartz de 32,768 kHz avec deux 22 pF, et 100 nF sur VDD, se retrouvent dans les 4 projets ci-dessus, de 3 auteurs différents. C'est un bon signe pour cette partie. Les différences (SENB, entrée d'antenne, filtrage de l'alimentation) sont les choix à trancher.

Le quartz choisi est prévu pour une charge de 12,5 pF. Le calcul habituel (deux 22 pF en série, plus environ 3 pF de la carte) donne environ 14 pF : le quartz tournerait un peu lentement, de l'ordre de 10 à 20 millionièmes (estimation faite avec des valeurs typiques de quartz, pas celles de ce quartz). Mais Skyworks fait exactement pareil dans sa note AN299 (pour le Si4700) : un quartz de 12,5 pF avec deux 22 pF.

Ce sont des projets publiés et documentés, souvent sérieux, mais seul l'essai sur prototype prouve qu'un montage marche. Les noms sont ceux des dépôts sources donnés par le jeu de données (probablement sur GitHub, pas vérifié d'ici).

Réponse :

### 2. L'entrée FM
La piste de la prise d'antenne au tuner mesure environ 1 cm, en 0,25 mm de large (pas adaptée à 50 Ω).
**Est-ce gênant à 100 MHz, ou est-ce négligeable sur cette longueur ?**

kicad-happy note aussi qu'aucune protection contre les décharges électrostatiques n'est prévue sur la prise d'antenne J2 (seule la prise USB en a une). **Faut-il en ajouter une, pour une antenne que l'on touche ?**

Réponse :

### 3. L'antenne AM
Une antenne ferrite se branche sur J3, à travers 470 nF.
**Quelle antenne ferrite choisir (inductance, taille) pour ce tuner ?**

Réponse :

### 4. La liaison tuner → ampli
Le tuner demande au moins 10 kΩ de charge sur ses sorties audio. La fiche du PAM8403 ne donne pas sa résistance d'entrée en clair (voir plus bas). La simulation donne 14 kΩ si l'ampli fait 20 kΩ (bon), et 8,3 kΩ s'il fait 10 kΩ (trop faible). La sortie gauche va aussi vers une entrée de mesure de l'ESP32.
**Faut-il un étage tampon, ou des résistances en série ?**

Ce que dit la fiche du PAM8403 (Power Analog Microelectronics, version de mars 2007, relue le 25/10/2026) : une formule du gain, AV = 20 log [2 × (Rf / Ri) × 1,4], avec Rf de 85 kΩ au plus et Ri de 15 kΩ au moins, pour 24 dB au plus. Lecture probable, à confirmer : Ri est dans la puce (15 kΩ), et une résistance mise en série devant l'entrée s'y ajoute. Sans résistance, l'ampli présenterait alors environ 15 kΩ au tuner, qui verrait en tout environ 11 kΩ (estimation tirée des deux cas de la simulation) : juste au-dessus des 10 kΩ demandés. Avec 10 kΩ en série, l'ampli présenterait 25 kΩ, et le gain passerait de 24 à environ 19,6 dB. Une réponse du forum Electronics Stack Exchange donne d'autres chiffres (Rf de 142 kΩ dans la puce, Ri d'au moins 18 kΩ : https://electronics.stackexchange.com/q/621155). **Est-ce la bonne lecture de la fiche ?**

Ce que montrent des montages publiés : une version de `ralphxavier/SI4735` met une résistance de 10 kΩ en série entre chaque sortie du tuner et l'ampli ; deux projets avec un PAM8403 (`rh1tech/frank`, `Byter64/Hans2`) mettent aussi 10 kΩ en série devant ses entrées. Avec 10 kΩ en série, le tuner voit au moins 10 kΩ, quelle que soit la résistance d'entrée de l'ampli ; le son est un peu plus faible.

Fennec, sur hackaday.io, fait autrement : 100 nF en série à la sortie du tuner, puis 100 nF et 1 kΩ devant chaque entrée du PAM8403. Et sa sortie gauche va aussi vers l'entrée GPIO1 de l'ESP32-S3, pour mesurer le son : exactement comme notre liaison vers IO1. Deux façons de faire publiées, donc : c'est à l'électronicien de trancher.

Réponse :

### 5. Le régulateur 3,3 V (AMS1117, linéaire)
D'après le calcul, il va jusqu'à environ 0,33 A ; vers 0,25 A, la puce est autour de 104 °C. L'ESP32-S3 tire des pointes de courant quand il émet en WiFi.
**Garder ce régulateur pour un prototype, ou passer tout de suite à un régulateur à découpage ?**

Fennec, sur hackaday.io, fait tourner un ESP32-S3 avec le WiFi allumé, un écran et le tuner sur un régulateur linéaire (LF33) depuis 5 V. Ça montre que c'est courant, pas que notre régulateur et son boîtier tiennent la chaleur.

kicad-happy compte une seule via sous la languette du régulateur (reliée au 3,3 V), et en conseille au moins 5, pour mener la chaleur vers le dessous. Mais le dessous de la carte est le plan de masse : ces vias demanderaient une surface de 3,3 V sous le régulateur, prise sur la masse. **Si on garde ce régulateur : faut-il ces vias et cette surface ?**

Une solution de rechange est déjà essayée sur une copie de la carte (pas sur celle que vous relisez) : le régulateur à découpage d'une carte libre d'Olimex, l'ESP32-S3-DevKit-LiPo (CERN-OHL-S-2.0), repris avec son routage. C'est un SY8089 (2 A), avec une bobine de 2,2 µH, 22 µF à l'entrée et à la sortie, et un pont de 220 kΩ et 49,9 kΩ (3,25 V). Ce sont les valeurs les plus courantes dans les montages publiés (jeu Open Schematics, 6 auteurs avec un SY8089 : 2,2 µH chez 4 d'entre eux, 22 µF à l'entrée chez 3, 220 kΩ en haut du pont chez 2 ; détail dans `resultats/radio-v4/montages-reels/montages.txt`). Il prend la place de l'AMS1117 et de ses deux 22 µF. KiCad n'y trouve aucune erreur, et aucune liaison ne manque. Pertes estimées : environ 0,15 W au lieu de 0,43 W, soit la puce vers 60 °C au lieu d'environ 104 °C (avec 85 % de rendement, une hypothèse : la courbe de la fiche n'a pas de chiffres lisibles). Mais il découpe vers 1 à 1,5 MHz (1,5 MHz d'après la fiche de Silergy, 1 MHz d'après la fiche de JLCPCB) : en plein dans la bande AM des ondes moyennes (0,53 à 1,7 MHz) que reçoit le tuner. **Faut-il partir sur ce montage pour le prototype, ou garder un régulateur linéaire, plus silencieux, pour une radio ?**

Réponse :

### 6. L'ampli PAM8403
À pleine puissance continue sur 4 Ω, le calcul dit qu'il atteint sa protection thermique. Avec de la musique, ça passe.
**La surface de cuivre autour de l'ampli suffit-elle ? Faut-il prévoir des haut-parleurs de 8 Ω ?**

**Le découpage de l'ampli et la bande AM** (ajouté le 25/10/2026). Le PAM8403 est un ampli de classe D sans filtre : d'après sa fiche, il découpe entre 250 et 450 kHz (350 kHz typique). Les multiples de cette fréquence (par exemple 700, 1 050 et 1 400 kHz, pour 350 kHz) tombent dans la bande AM des ondes moyennes (531 à 1 701 kHz) que reçoit le tuner. C'est le même souci qu'à la question 5, mais l'ampli est sur toutes les versions de la carte. Sans filtre de sortie, la fiche conseille une perle de ferrite sur chaque fil de haut-parleur, qui « réduit les parasites vers 1 MHz et au-delà » (traduit), et son schéma montre une perle et un condensateur de 200 pF sur chaque sortie. Sur notre carte, les sorties de l'ampli vont directement aux prises J4 et J5. **Faut-il prévoir ces emplacements (perles et condensateurs) avant de commander ? Où placer l'antenne ferrite et les fils des haut-parleurs par rapport à l'ampli ?**

Le plan de test (version 2.4, essai 8) mesure ce bruit sur toute la bande AM, ampli muet puis actif. La piste vient d'une question du forum Electronics Stack Exchange (https://electronics.stackexchange.com/q/684386), vérifiée ensuite sur la fiche.

Réponse :

### 7. Les masses
Deux couches, un plan de masse dessous, partagé par l'ESP32 (WiFi), le tuner et l'ampli.
**Risque-t-on du bruit dans la radio ? Faut-il séparer les masses ou éloigner un bloc ?** Faut-il, comme dans pico-radio-5, une inductance de filtrage sur l'alimentation du tuner ?

Réponse :

### 8. La prise USB-C
Deux pastilles de masse ont été raccourcies de 0,02 mm, pour respecter la règle du fabricant (0,2 mm entre un trou et le cuivre).
**Est-ce sans risque pour la soudure et la tenue de la prise ?**

Réponse :

### 9. Le démarrage du tuner
Au reset, le tuner choisit son mode de bus : il lui faut RADIO_INT à 0 (résistance interne de 1 MΩ, d'après la fiche du Si4735) et SCL à 1 (résistance de tirage de 4,7 kΩ côté ESP32).
**Est-ce suffisant, ou faut-il une résistance vers la masse sur RADIO_INT ?**

Fennec ne relie pas GPO2/INT et pilote le tuner avec la bibliothèque Arduino « PU2CLR SI4735 » : elle marche donc avec le Si4732-A10.

Réponse :

### 10. Les trous de fixation
Quatre trous M3, métallisés et reliés à la masse, ont été ajoutés le 23/10/2026. La chaîne les a mis là où aucun bloc ni aucune liaison entre blocs ne passe : tous en haut de la carte, qui a grandi de 7 mm pour ça. Le trou du coin en haut à gauche est à environ 6 mm au-dessus de la zone réservée à l'antenne de l'ESP32-S3.
**Ce trou relié à la masse gêne-t-il l'antenne ? Faut-il le laisser non métallisé, ou prévoir une vis en nylon ?** La carte n'a pas de trou en bas : est-ce acceptable pour la tenue (boîtier, prise USB qu'on branche) ?

Réponse :

### 11. Les condensateurs sur le 5 V de l'USB
La liaison VBUS porte environ 33 µF en tout : 22 µF à l'entrée du régulateur, puis 10 µF, 1 µF et deux 100 nF (un peu moins en réalité sous 5 V). D'après une note de Nuvoton qui reprend la règle de l'USB-IF pour l'USB 2.0, la charge prise au branchement ne doit pas dépasser 50 µC, soit 10 µF sous 5 V.
**Faut-il réduire ces condensateurs, ou ajouter un démarrage progressif ? Ou est-ce sans conséquence pour une radio branchée sur un chargeur ?**

Réponse :

### 12. Les lignes USB de l'ESP32-S3
D+ et D- vont directement de la prise USB-C au module, en passant par la protection USBLC6. Le guide de conception d'Espressif pour l'ESP32-S3 recommande de prévoir sur ces deux lignes des résistances en série (22 ou 33 Ω pour commencer) et des condensateurs vers la masse (qu'on peut laisser vides au début), près de la puce.
**Faut-il ajouter ces emplacements avant de commander ?**

Réponse :

## Autres remarques

(À noter ici : tout ce que la personne a vu et qui n'est pas dans les questions.)

## Relecture

| Date | Qui | Questions vues | Suite donnée |
|---|---|---|---|
| | | | |

Après la relecture, les réponses vont dans `METHODE-CARTES-PUZZLE.md` (ce qui a été appris) et le niveau de confiance de la carte passe à « relue par un électronicien ».

## Historique

- **1.8 — 25/10/2026** : question 4 : ce que dit la fiche du PAM8403 sur sa résistance d'entrée (formule du gain, Ri d'au moins 15 kΩ), avec une lecture à confirmer. Question 5 : les valeurs du régulateur d'Olimex sont les plus courantes dans les montages publiés. Question 6 : le découpage de l'ampli (250 à 450 kHz) dans la bande AM, les perles de ferrite et les condensateurs de 200 pF que conseille sa fiche, et l'essai 8 du plan de test. Pistes trouvées par la recherche des pièges connus (`outils/chercher_fonction.py`, Electronics Stack Exchange), puis vérifiées sur la fiche. Toujours 12 questions.
- **1.7 — 25/10/2026** : question 5 : la solution de rechange essayée sur une copie de la carte (régulateur à découpage SY8089 repris d'une carte libre d'Olimex), et la question du bruit de découpage pour le tuner. Toujours 12 questions.
- **1.6 — 25/10/2026** : le deuxième avis de kicad-happy, lancé pour de vrai sur les machines de GitHub, dans « Ce que la chaîne a déjà vérifié » ; ses deux remarques utiles aux questions 2 (protection de la prise d'antenne) et 5 (vias sous le régulateur). Toujours 12 questions.
- **1.5 — 24/10/2026** : questions 11 (condensateurs sur le 5 V de l'USB) et 12 (lignes USB de l'ESP32-S3), trouvées en refaisant à la main les contrôles de l'outil kicad-happy ; le calcul de charge du quartz et la note AN299 de Skyworks à la question 1 ; les nouveaux contrôles de la chaîne dans « Ce que la chaîne a déjà vérifié ».
- **1.4 — 23/10/2026** : question 10, les trous de fixation (place, antenne, tenue).
- **1.3 — 23/10/2026** : ligne de concordance à la question 1 (4 projets de 3 auteurs font pareil pour le quartz et le découplage).
- **1.2 — 23/10/2026** : ajout de la radio Fennec (hackaday.io), très proche de la nôtre, aux questions 1, 4, 5 et 9.
- **1.1 — 23/10/2026** : ajout de ce que montrent des montages publiés (jeu Open Schematics) pour les questions 1, 4 et 7.
- **1.0 — 23/10/2026** : première version, à partir des points que la chaîne n'a pas pu vérifier.
