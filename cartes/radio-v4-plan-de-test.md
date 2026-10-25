# Carte radio RADIONÉO v4 — plan de test à la réception

Exylia Project — version 2.4 — 25 octobre 2026

La carte v4 est la v3 avec un autre tuner : le **Si4732-A10** (boîtier SOIC-16) remplace le Si4735, en rupture de stock. La prise d'antenne FM change aussi (BWSMA-KWE-Z001). Les numéros des sorties TP sont les mêmes qu'en v3. Depuis le 23/10/2026, la carte a quatre trous de fixation M3 (H1 à H4), métallisés et reliés à la masse ; elle mesure 80 × 73 mm.

Ce plan sert à vérifier une carte reçue de l'usine. On va du plus sûr au plus risqué : d'abord sans courant, ensuite sous tension, enfin avec un programme d'essai. À chaque étape, la valeur attendue est donnée. Si une mesure ne correspond pas, **on s'arrête** et on note ce qu'on a trouvé avant d'aller plus loin.

Les « sorties » (pastilles TP) servent de points de mesure : ce sont des pastilles de cuivre nu, assez grandes pour y poser une pointe de multimètre.

## Matériel

- Un multimètre avec bip de continuité. Un modèle qui annonce les valeurs à voix haute est idéal.
- Un câble USB-C et un ordinateur. Pour l'essai de l'ampli à fort volume : un chargeur USB-C d'au moins 2 A. À pleine puissance, l'ampli et l'ESP32 demandent environ 1,7 A.
- De préférence, un testeur USB à placer entre le câble et la carte, qui affiche le courant consommé (avec l'aide de quelqu'un pour le lire, s'il ne parle pas).
- Deux haut-parleurs de 4 à 8 Ω, un bout de fil comme antenne FM, et l'antenne ferrite de l'AM (sur J3).
- Quelqu'un qui voit, pour l'étape 1 et pour lire le testeur USB.
- De préférence, le banc de test à pointes (étape 6 de la chaîne, dossier `resultats/radio-v4/banc-test/`) : il évite de viser les pastilles.

## Repères sur la carte

| Sortie | Liaison | Bloc |
|---|---|---|
| TP1 | AMP_MUTE (coupure de l'ampli) | alimentation et ESP32 (A) |
| TP2 | VBUS (5 V de l'USB) | A |
| TP3 / TP4 | I2C_SDA / I2C_SCL | A |
| TP5 / TP6 | RADIO_RST / RADIO_INT | A |
| TP7 | 3V3 | A |
| TP8 | LOUT (son gauche, vers la mesure audio) | A |
| TP9 / TP10 | I2C_SDA / I2C_SCL | tuner (B) |
| TP11 / TP12 | RADIO_RST / RADIO_INT | B |
| TP13 | 3V3 | B |
| TP14 / TP15 | LOUT / ROUT | B |
| TP16 / TP17 | LOUT / ROUT | ampli (C) |
| TP18 | VBUS | C |
| TP19 | AMP_MUTE | C |

La masse (GND) se prend sur la couronne de cuivre d'un trou de fixation (H1 à H4), sur l'une des broches GND de la prise de la molette J6 (broche 2), ou sur le corps métallique de la prise USB-C.

**Avec le banc de test à pointes.** La sortie TP*n* arrive sur la borne *n*, au fond d'un entonnoir rond, avec son numéro en braille et en chiffres en relief ; la masse arrive sur l'entonnoir carré « masse ». Les bornes sont en rangées, de gauche à droite et de haut en bas, coin coupé en haut à gauche. Toutes les mesures des étapes 2, 3 et 4 se font dans les entonnoirs, carte posée dans le socle et écrous papillon serrés. La notice du banc est `banc-test/banc-test.txt`.

## 1. Regarder la carte (avec une personne qui voit)

- Tous les composants sont posés, aucun ne manque ni n'est de travers.
- Pas de goutte de soudure entre deux broches, surtout sur la puce du tuner (U4) et sur l'ampli (U5). Les deux ont 16 broches espacées de 1,27 mm.
- La puce du tuner (U4), celle de l'ampli (U5), le régulateur (U2) et la protection USB (U1) sont dans le bon sens. Le repère de la broche 1 doit correspondre au dessin de la carte.
- La prise d'antenne FM (J2) est droite, avec sa partie filetée tournée vers le bord droit de la carte.

**Mesures guidées.** Les étapes 2, 3 et 4 peuvent se faire avec `outils/mesures_guidees.py` : il annonce chaque mesure (dans quels entonnoirs du banc mettre les pointes), lit la valeur sur le multimètre par sigrok s'il est reconnu, sinon on la tape, dit si elle est bonne, et range tout dans un fichier daté. Commande, depuis le dossier de la chaîne :

```
python3 outils/mesures_guidees.py cartes/radio-v4-mesures.json resultats/radio-v4/
```

Ce que la réponse doit contenir : d'abord « MESURES GUIDÉES — RADIONÉO carte radio v4 », puis le titre de l'étape 2 ; à la fin, « Résultats rangés dans : » suivi du nom du fichier. Avec un multimètre reconnu par sigrok, ajouter `--multimetre` et son pilote (liste : `sigrok-cli -L`).

## 2. Sans courant : pas de court-circuit

Multimètre en position bip de continuité, carte **débranchée**.

| Entre | Attendu |
|---|---|
| TP2 (5 V) et GND | pas de bip continu. Un bip très court au début est normal : les condensateurs se chargent. |
| TP7 (3,3 V) et GND | pas de bip continu |
| TP2 (5 V) et TP7 (3,3 V) | pas de bip continu |

**Si ça bipe en continu : ne pas brancher la carte.** Il y a un court-circuit à trouver d'abord.

## 3. Sans courant : les liaisons entre blocs

Ce sont les liaisons tracées par Freerouting. Ce test vérifie exactement la partie automatique de la chaîne. Chaque paire doit **biper**.

| Entre | Liaison |
|---|---|
| TP2 et TP18 | 5 V vers l'ampli |
| TP7 et TP13 | 3,3 V vers le tuner |
| TP3 et TP9 | I2C_SDA |
| TP4 et TP10 | I2C_SCL |
| TP5 et TP11 | RADIO_RST |
| TP6 et TP12 | RADIO_INT |
| TP1 et TP19 | AMP_MUTE |
| TP8, TP14 et TP16 | LOUT : les trois ensemble |
| TP15 et TP17 | ROUT |

Pour vérifier qu'il n'y a pas de court-circuit entre liaisons voisines, on teste aussi des paires qui ne doivent **pas** biper :
- TP3 et TP4 ;
- TP5 et TP6 ;
- TP14 et TP15.

## 4. Première mise sous tension

Brancher la carte en USB-C, si possible à travers le testeur USB, et **sans haut-parleurs**.

| Mesure | Attendu | Si ce n'est pas le cas |
|---|---|---|
| Courant consommé | quelques dizaines de mA, sous 0,2 A | au-delà, ou si quelque chose chauffe : débrancher tout de suite |
| Tension entre TP2 et GND | 5 V, de 4,75 à 5,25 V | câble ou chargeur en cause, ou chute dans la protection U1 |
| Tension entre TP7 et GND | 3,3 V, de 3,2 à 3,4 V | régulateur U2 à vérifier |
| Tension entre TP13 et GND | la même que TP7 | liaison 3,3 V vers le tuner coupée |
| Tension entre TP18 et GND | la même que TP2 | liaison 5 V vers l'ampli coupée |
| Tension entre TP1 et GND | 0 V | normal : la résistance R7 tient l'ampli muet |

**Échauffement du régulateur U2.** Le calcul de la chaîne (étape 0 bis) le donne autour de 100 °C dans la puce si la carte tire 0,25 A, et trop chaud au-delà d'environ 0,33 A. Après 5 minutes de marche, WiFi allumé :
- noter le courant consommé (testeur USB) : c'est le vrai chiffre qui remplace l'hypothèse de 0,25 A ;
- toucher U2 brièvement, du bout du doigt, **carte posée et sans la tenir** : tiède à chaud, c'est normal ; si on ne peut pas garder le doigt dessus, le noter et débrancher.

## 5. L'ESP32 et l'ordinateur

- Brancher la carte sur l'ordinateur. Elle doit apparaître comme un appareil USB d'Espressif (identifiant 303A).
- Si rien n'apparaît : garder **BOOT** (SW2) appuyé, appuyer puis relâcher **RESET** (SW1), puis relâcher BOOT. La puce passe alors en mode programmation.
- Commande de vérification, sur l'ordinateur :

  ```
  esptool.py chip_id
  ```

  Avec les versions récentes d'esptool, la commande s'écrit `esptool chip-id`. La réponse doit contenir « ESP32-S3 ». Sinon, noter le message d'erreur.

## 6. Programme d'essai (`cartes/radio-v4-essai/`)

Le programme (version 1.1) est écrit et compile (PlatformIO, bibliothèque PU2CLR SI4735 2.1.8) ; il n'a pas encore tourné sur une vraie carte. Ses broches viennent du schéma, par `scripts/broches_esp32.py`. Il fait les essais du tableau ci-dessous l'un après l'autre, annonce chacun en français sur le port série (lisible par un lecteur d'écran), pose une question (répondre « o » ou « n »), et donne un bilan à recopier dans le tableau « Résultats ».

Commandes, depuis le dossier de la chaîne, carte branchée en USB :

```
pio run -d cartes/radio-v4-essai -t upload
pio device monitor -d cartes/radio-v4-essai
```

Ce que la réponse doit contenir : la première se termine par « SUCCESS » ; la seconde affiche « PROGRAMME D'ESSAI DE LA CARTE RADIO RADIONÉO V4. ». Si la carte n'est pas trouvée, passer en mode programmation (étape 5 : BOOT appuyé, RESET, relâcher BOOT) et recommencer.

Un petit programme pour l'ESP32-S3, qui fait les essais l'un après l'autre et les annonce sur le port série (lisible par un lecteur d'écran) :

| Essai | Ce que fait le programme | Attendu |
|---|---|---|
| LED | fait clignoter la LED D1 (IO48) | la LED clignote : à faire vérifier par une personne qui voit, ou avec un détecteur de lumière sonore |
| Molette | lit IO4, IO5 (rotation) et IO6 (appui), avec les résistances de tirage internes de l'ESP32 activées | chaque cran et chaque appui sont annoncés |
| Bus I2C | met RADIO_RST (IO12) à 0, laisse RADIO_INT (IO13) en entrée **sans résistance de tirage vers le haut**, garde SCL (IO11) à 1, puis remet RADIO_RST à 1 ; cherche ensuite les appareils sur SDA (IO10) et SCL (IO11) | un seul appareil, le tuner, à l'adresse 0x11 (broche SENB à la masse, d'après la note AN332 de Silicon Labs). Pourquoi ces précautions : au moment où RST remonte, le tuner choisit son mode de bus. Pour l'I2C, il lui faut GPO2/INT à 0 et SCL à 1. Une résistance interne de 1 MΩ tire INT vers 0 pendant la remise à zéro ; un tirage vers le haut côté ESP32 la contredirait. Ceci vient de la fiche du Si4735, de la même famille : la fiche courte du Si4732 n'en parle pas. |
| Tuner | démarre le tuner en FM et règle une station locale connue ; puis essaie une station en ondes moyennes (AM), avec l'antenne ferrite sur J3 | le tuner répond aux commandes et indique la force du signal |
| Son du tuner | mesure la tension alternative entre TP14 et GND, au multimètre en volts alternatifs | quelques dizaines de millivolts, de l'ordre de 0,08 V selon la fiche du Si4735. La fiche courte du Si4732 ne donne pas ce chiffre : c'est à mesurer. |
| Mesure audio | lit IO1 (AUDIO_SENSE) | autour de la moitié de 3,3 V au repos, qui bouge avec le son |
| Ampli | haut-parleurs branchés sur J4 et J5, met AMP_MUTE (IO9) à 1 | la radio s'entend ; à 0, silence. Au volume maximum, la puce U5 chauffe : sa protection coupe le son vers 120 °C, puis le remet quand elle refroidit. C'est attendu à pleine puissance sur 4 Ω, d'après le calcul de la chaîne. Si un « boum » se fait entendre quand le son revient, le noter : le projet Fennec (hackaday.io) attend 80 ms avant de remettre le son, et conseille de vérifier le sens de la commande de l'ampli. |
| Bruit de l'ampli en AM | antenne ferrite sur J3, posée là où elle sera dans le boîtier, haut-parleurs branchés ; son du tuner à zéro, relève la force du signal sur les 131 canaux AM (531 à 1 701 kHz), ampli muet, puis actif, puis muet encore (environ 40 secondes, on n'entend rien) | aucun canal plus fort de 6 dB quand l'ampli est actif. Pourquoi : le PAM8403 découpe entre 250 et 450 kHz (d'après sa fiche), et ses multiples tombent dans la bande AM. Si des canaux montent, le programme les nomme : les noter, c'est la question 6 de la fiche pour l'électronicien (perles de ferrite et condensateurs sur les sorties, place de l'antenne). Le programme donne aussi le bruit moyen de la bande, ampli muet : à comparer avec la copie de la carte qui a le régulateur à découpage (question 5). |

## 7. Ce qui reste à vérifier sur cette carte

- **L'impédance d'entrée de l'ampli PAM8403.** Le tuner demande au moins 10 kΩ de charge sur LOUT. Si le son du tuner est faible ou déformé à l'essai 6, c'est la première piste. D'après la formule du gain de sa fiche, l'ampli présenterait environ 15 kΩ (lecture à confirmer : fiche de questions, question 4).
- **Le découpage de l'ampli dans la bande AM.** Les sorties de l'ampli n'ont ni perle de ferrite ni condensateur, alors que sa fiche en conseille quand il n'y a pas de filtre de sortie. L'essai 8 mesure si ce découpage arrive dans la radio.
- **La prise USB-C** : ses deux pastilles de masse ont été raccourcies de 0,02 mm, pour la règle de JLCPCB. Vérifier que la prise est bien soudée et tient.
- **Le tuner Si4732-A10** : il est de la même famille que le Si4735, mais sa fiche publique ne fait que 3 pages. Le montage (quartz de 32,768 kHz avec deux 22 pF, découplage de 100 nF près de VDD, plus 10 µF à l'entrée du 3,3 V) reprend celui du Si4735. La bibliothèque Arduino « PU2CLR SI4735 » sert aussi pour le Si4732 : le projet Fennec (hackaday.io, ESP32-S3 + Si4732-A10 + PAM8403) l'utilise telle quelle, avec le cœur ESP32 2.0.10 pour Arduino (il ne compile pas avec la version 3).
- **Le serrage de l'antenne FM** : le bout fileté de J2 s'arrête à environ 0,7 mm du bord de la carte. Vérifier qu'on peut visser un câble ou une antenne sans que l'écrou touche la carte.

## Résultats

| Étape | Date | Résultat | Remarques |
|---|---|---|---|
| 1. Regarder | | | |
| 2. Pas de court-circuit | | | |
| 3. Liaisons entre blocs | | | |
| 4. Mise sous tension | | | |
| 5. ESP32 et ordinateur | | | |
| 6. Programme d'essai | | | |

## Historique

- **2.4 — 25/10/2026** : essai 8 du programme d'essai (version 1.1, compilé, pas encore essayé sur une carte) : le bruit du découpage de l'ampli dans la bande AM, ampli muet puis actif ; l'antenne ferrite dans le matériel ; l'impédance d'entrée de l'ampli d'après sa fiche. Piste trouvée par la recherche des pièges connus (`outils/chercher_fonction.py`), puis vérifiée sur la fiche du PAM8403.
- **2.3 — 23/10/2026** : programme d'essai écrit et compilé (`cartes/radio-v4-essai/`) ; mesures guidées pour les étapes 2 à 4 (`outils/mesures_guidees.py`, sigrok ou clavier).
- **2.2 — 23/10/2026** : trous de fixation reliés à la masse (prise de masse facile) ; mesures possibles avec le banc de test à pointes.
- **2.1 — 23/10/2026** : la bibliothèque PU2CLR SI4735 est utilisée avec un Si4732 par le projet Fennec (hackaday.io) ; conseil repris de Fennec pour l'essai de l'ampli.
- **2.0 — 23/10/2026** : carte v4, avec le tuner Si4732-A10 et la prise d'antenne BWSMA-KWE-Z001. Ajout des précautions de démarrage du bus I2C, de l'essai en AM et du serrage de l'antenne.
- **1.1 — 23/10/2026** : ajout de la vérification d'échauffement du régulateur U2 et du chargeur d'au moins 2 A.
- **1.0 — 23/10/2026** : première version. Les numéros de sorties et de broches sont relevés sur la carte produite par la chaîne puzzle v1.6.
