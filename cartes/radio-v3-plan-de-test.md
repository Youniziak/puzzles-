# Carte radio RADIONÉO v3 — plan de test à la réception

Exylia Project — version 1.1 — 23 octobre 2026

Ce plan sert à vérifier une carte reçue de l'usine. On va du plus sûr au plus risqué : d'abord sans courant, ensuite sous tension, enfin avec un programme d'essai. À chaque étape, la valeur attendue est donnée. Si une mesure ne correspond pas, **on s'arrête** et on note ce qu'on a trouvé avant d'aller plus loin.

Les « sorties » (pastilles TP) servent de points de mesure : ce sont des pastilles de cuivre nu, assez grandes pour y poser une pointe de multimètre.

## Matériel

- Un multimètre avec bip de continuité. Un modèle qui annonce les valeurs à voix haute est idéal.
- Un câble USB-C et un ordinateur. Pour l'essai de l'ampli à fort volume : un chargeur USB-C d'au moins 2 A. À pleine puissance, l'ampli et l'ESP32 demandent environ 1,7 A.
- De préférence, un testeur USB à placer entre le câble et la carte, qui affiche le courant consommé (avec l'aide de quelqu'un pour le lire, s'il ne parle pas).
- Deux haut-parleurs de 4 à 8 Ω, et un bout de fil comme antenne FM.
- Quelqu'un qui voit, pour l'étape 1 et pour lire le testeur USB.

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

La masse (GND) se prend sur l'une des broches GND de la prise de la molette J6 (broche 2), ou sur le corps métallique de la prise USB-C.

## 1. Regarder la carte (avec une personne qui voit)

- Tous les composants sont posés, aucun ne manque ni n'est de travers.
- Pas de goutte de soudure entre deux broches, surtout sur la puce du tuner (U4) et sur l'ampli (U5), dont les broches sont fines.
- La puce de l'ampli (U5), le régulateur (U2) et la protection USB (U1) sont dans le bon sens. Le repère de la broche 1 doit correspondre au dessin de la carte.

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

## 6. Programme d'essai (à écrire, Claude peut le faire)

Un petit programme pour l'ESP32-S3, qui fait les essais l'un après l'autre et les annonce sur le port série (lisible par un lecteur d'écran) :

| Essai | Ce que fait le programme | Attendu |
|---|---|---|
| LED | fait clignoter la LED D1 (IO48) | la LED clignote : à faire vérifier par une personne qui voit, ou avec un détecteur de lumière sonore |
| Molette | lit IO4, IO5 (rotation) et IO6 (appui), avec les résistances de tirage internes de l'ESP32 activées | chaque cran et chaque appui sont annoncés |
| Bus I2C | met RADIO_RST (IO12) à 0, laisse RADIO_INT (IO13) en entrée, puis remet RADIO_RST à 1 ; cherche les appareils sur SDA (IO10) et SCL (IO11) | un seul appareil, le tuner, à l'adresse 0x11 (broche SEN à la masse, d'après la note AN332 de Silicon Labs) |
| Tuner | démarre le tuner en FM et règle une station locale connue | le tuner répond aux commandes et indique la force du signal |
| Son du tuner | mesure la tension alternative entre TP14 et GND, au multimètre en volts alternatifs | quelques dizaines de millivolts, de l'ordre de 0,08 V selon la fiche du Si4735 |
| Mesure audio | lit IO1 (AUDIO_SENSE) | autour de la moitié de 3,3 V au repos, qui bouge avec le son |
| Ampli | haut-parleurs branchés sur J4 et J5, met AMP_MUTE (IO9) à 1 | la radio s'entend ; à 0, silence. Au volume maximum, la puce U5 chauffe : sa protection coupe le son vers 120 °C, puis le remet quand elle refroidit. C'est attendu à pleine puissance sur 4 Ω, d'après le calcul de la chaîne. |

## 7. Ce qui reste à vérifier sur cette carte

- **L'impédance d'entrée de l'ampli PAM8403.** Le tuner demande au moins 10 kΩ de charge sur LOUT. Si le son du tuner est faible ou déformé à l'essai 6, c'est la première piste.
- **La prise USB-C** : ses deux pastilles de masse ont été raccourcies de 0,02 mm, pour la règle de JLCPCB. Vérifier que la prise est bien soudée et tient.

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

- **1.1 — 23/10/2026** : ajout de la vérification d'échauffement du régulateur U2 et du chargeur d'au moins 2 A.
- **1.0 — 23/10/2026** : première version. Les numéros de sorties et de broches sont relevés sur la carte produite par la chaîne puzzle v1.6.
