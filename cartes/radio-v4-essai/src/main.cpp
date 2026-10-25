// Programme d'essai de la carte radio RADIONÉO v4 — Exylia Project — version 1.1 — 25/10/2026
//
// Il suit l'étape 6 du plan de test (cartes/radio-v4-plan-de-test.md). Chaque essai est annoncé en français sur le
// port série (USB), lisible par un lecteur d'écran : ce que fait le programme, ce qui est attendu, puis la question.
// On répond « o » (oui) ou « n » (non) puis Entrée ; à la fin, le bilan se recopie dans le tableau « Résultats ».
// Les broches viennent de include/broches.h, écrit par la chaîne (scripts/broches_esp32.py) à partir du schéma.
// Repris de projets publiés : bibliothèque PU2CLR SI4735 (MIT) ; attente de 80 ms avant de rendre le son à l'ampli,
// conseil du projet Fennec (CiferTech, hackaday.io, MIT).
// Version 1.1 : essai 8, le bruit du découpage de l'ampli dans la bande AM (plan de test 2.4, fiche de questions 1.8).

#include <Arduino.h>
#include <Wire.h>
#include <SI4735.h>
#include "broches.h"

SI4735 tuner;

const int NB_ESSAIS = 8;
const char *noms[NB_ESSAIS] = {"LED", "Molette", "Bus I2C", "Tuner FM", "Tuner AM", "Son du tuner (IO1)", "Ampli",
                               "Bruit de l'ampli en AM"};
char resultats[NB_ESSAIS];            // 'o', 'n', ou '-' (pas fait)
bool tunerPret = false;

void dire(const char *texte) { Serial.println(texte); }

String lireLigne() {
  String s;
  while (true) {
    while (!Serial.available()) delay(10);
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (s.length()) return s;
    } else {
      s += c;
    }
  }
}

void attendreEntree() {
  dire("  (Entrée pour commencer)");
  lireLigne();
}

char reponse(const char *question) {
  while (true) {
    Serial.print("  QUESTION : ");
    Serial.print(question);
    Serial.println(" Répondre o ou n, puis Entrée.");
    String s = lireLigne();
    s.trim();
    s.toLowerCase();
    if (s == "o" || s == "oui") return 'o';
    if (s == "n" || s == "non") return 'n';
  }
}

// ---------- 1. LED
void essaiLED() {
  dire("");
  dire("ESSAI 1 SUR 8 : LA LED D1 (IO48).");
  dire("  Le programme fait clignoter la LED 10 fois, une fois par seconde.");
  dire("  Attendu : la LED clignote. À faire vérifier par une personne qui voit, ou avec un détecteur de lumière sonore.");
  attendreEntree();
  pinMode(BROCHE_LED_IO, OUTPUT);
  for (int i = 0; i < 10; i++) {
    digitalWrite(BROCHE_LED_IO, HIGH); delay(500);
    digitalWrite(BROCHE_LED_IO, LOW);  delay(500);
  }
  resultats[0] = reponse("La LED a-t-elle clignoté ?");
}

// ---------- 2. Molette
void essaiMolette() {
  dire("");
  dire("ESSAI 2 SUR 8 : LA MOLETTE (IO4, IO5, appui IO6), branchée sur J6.");
  dire("  Pendant 20 secondes, tourner la molette dans les deux sens et appuyer dessus.");
  dire("  Attendu : chaque cran est annoncé (« droite » ou « gauche »), et chaque appui.");
  attendreEntree();
  pinMode(BROCHE_ENC_A, INPUT_PULLUP);
  pinMode(BROCHE_ENC_B, INPUT_PULLUP);
  pinMode(BROCHE_ENC_SW, INPUT_PULLUP);
  int aAvant = digitalRead(BROCHE_ENC_A), swAvant = digitalRead(BROCHE_ENC_SW);
  int crans = 0, appuis = 0;
  unsigned long fin = millis() + 20000;
  while (millis() < fin) {
    int a = digitalRead(BROCHE_ENC_A), sw = digitalRead(BROCHE_ENC_SW);
    if (a != aAvant && a == LOW) {
      dire(digitalRead(BROCHE_ENC_B) == HIGH ? "  droite" : "  gauche");
      crans++;
    }
    if (sw != swAvant && sw == LOW) { dire("  appui"); appuis++; }
    aAvant = a; swAvant = sw;
    delay(1);
  }
  Serial.printf("  Vu : %d cran(s), %d appui(s).\n", crans, appuis);
  resultats[1] = reponse("Les crans et les appuis ont-ils été annoncés comme vous les avez faits ?");
}

// ---------- 3. Bus I2C, avec le démarrage du tuner en mode I2C
void demarrerTunerEnI2C() {
  // Au moment où RST remonte, le tuner choisit son mode de bus : il lui faut GPO2/INT à 0 (résistance interne de 1 MΩ,
  // donc pas de résistance de tirage côté ESP32) et SCL à 1 (bus I2C au repos).
  pinMode(BROCHE_RADIO_INT, INPUT);
  pinMode(BROCHE_RADIO_RST, OUTPUT);
  digitalWrite(BROCHE_RADIO_RST, LOW);
  Wire.begin(BROCHE_I2C_SDA, BROCHE_I2C_SCL);
  delay(10);
  digitalWrite(BROCHE_RADIO_RST, HIGH);
  delay(10);
}

void essaiI2C() {
  dire("");
  dire("ESSAI 3 SUR 8 : LE BUS I2C (SDA IO10, SCL IO11).");
  dire("  Le programme démarre le tuner en mode I2C, puis cherche les appareils sur le bus.");
  dire("  Attendu : un seul appareil, le tuner, à l'adresse 0x11 (broche SENB à la masse).");
  attendreEntree();
  demarrerTunerEnI2C();
  int trouves = 0;
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      Serial.printf("  appareil trouvé à l'adresse 0x%02X%s\n", a, a == 0x11 ? " : c'est le tuner" : "");
      trouves++;
    }
  }
  if (!trouves) dire("  aucun appareil trouvé.");
  resultats[2] = (trouves == 1) ? 'o' : 'n';
  Serial.printf("  Résultat : %s\n", resultats[2] == 'o' ? "bon" : "pas bon (voir le plan de test, étape 6)");
}

// ---------- 4 et 5. Tuner
void annoncerSignal(const char *bande, float frequence, const char *unite) {
  tuner.getCurrentReceivedSignalQuality();
  Serial.printf("  %s : %.1f %s, force du signal %d dBµV, rapport signal sur bruit %d dB\n",
                bande, frequence, unite, tuner.getCurrentRSSI(), tuner.getCurrentSNR());
}

void essaiFM() {
  dire("");
  dire("ESSAI 4 SUR 8 : LE TUNER EN FM, antenne (un bout de fil) vissée sur J2.");
  dire("  Le programme démarre le tuner en FM, puis cherche 5 stations, une par une.");
  dire("  Attendu : le tuner répond, et au moins une station a une force de signal nettement au-dessus des autres.");
  attendreEntree();
  if (tuner.getDeviceI2CAddress(BROCHE_RADIO_RST) == 0) {
    dire("  Le tuner ne répond pas sur le bus I2C.");
    resultats[3] = 'n';
    return;
  }
  tuner.setup(BROCHE_RADIO_RST, 0);          // 0 : FM
  tuner.setFM(8750, 10800, 8750, 10);         // de 87,5 à 108 MHz, pas de 100 kHz
  tunerPret = true;
  delay(500);
  annoncerSignal("départ", tuner.getFrequency() / 100.0, "MHz");
  for (int i = 0; i < 5; i++) {
    tuner.seekStationUp();
    delay(300);
    annoncerSignal("station", tuner.getFrequency() / 100.0, "MHz");
  }
  resultats[3] = reponse("Le tuner a-t-il répondu, avec au moins une station au signal fort ?");
}

void essaiAM() {
  dire("");
  dire("ESSAI 5 SUR 8 : LE TUNER EN ONDES MOYENNES (AM), antenne ferrite branchée sur J3.");
  dire("  Le programme passe en AM et cherche 3 stations.");
  dire("  Attendu : le tuner répond. Selon le lieu et l'heure, il peut n'y avoir aucune station forte : le noter.");
  attendreEntree();
  if (!tunerPret) { dire("  Essai FM pas réussi : essai AM sauté."); resultats[4] = '-'; return; }
  tuner.setAM(520, 1710, 1000, 9);            // de 520 à 1710 kHz, pas de 9 kHz (Europe)
  delay(500);
  annoncerSignal("départ", tuner.getFrequency(), "kHz");
  for (int i = 0; i < 3; i++) {
    tuner.seekStationUp();
    delay(300);
    annoncerSignal("station", tuner.getFrequency(), "kHz");
  }
  resultats[4] = reponse("Le tuner a-t-il répondu en AM ?");
  tuner.setFM(8750, 10800, 8750, 10);
  tuner.seekStationUp();
}

// ---------- 6. Son du tuner, mesuré par l'ESP32 sur IO1
void essaiSon() {
  dire("");
  dire("ESSAI 6 SUR 8 : LE SON DU TUNER, mesuré sur IO1 (AUDIO_SENSE).");
  dire("  Le programme mesure pendant 2 secondes, sur une station FM.");
  dire("  Attendu : une tension moyenne vers 1,65 V (la moitié de 3,3 V), qui bouge avec le son de quelques dizaines de mV.");
  attendreEntree();
  if (!tunerPret) { dire("  Tuner pas démarré : essai sauté."); resultats[5] = '-'; return; }
  tuner.setVolume(40);
  long somme = 0; int n = 0, mini = 4000, maxi = 0;
  unsigned long fin = millis() + 2000;
  while (millis() < fin) {
    int mv = analogReadMilliVolts(BROCHE_AUDIO_SENSE);
    somme += mv; n++;
    mini = min(mini, mv); maxi = max(maxi, mv);
    delayMicroseconds(200);
  }
  Serial.printf("  Moyenne %ld mV, du plus bas au plus haut : %d mV (%d mesures)\n", somme / n, maxi - mini, n);
  resultats[5] = (somme / n > 1000 && somme / n < 2300 && maxi - mini > 10) ? 'o' : 'n';
  Serial.printf("  Résultat : %s\n", resultats[5] == 'o' ? "bon" : "à regarder (plan de test, section 7 : charge de la sortie du tuner)");
}

// ---------- 7. Ampli
void essaiAmpli() {
  dire("");
  dire("ESSAI 7 SUR 8 : L'AMPLI, haut-parleurs branchés sur J4 et J5.");
  dire("  Le programme rend le son pendant 10 secondes, puis le coupe.");
  dire("  Attendu : la radio s'entend, puis le silence. Noter un éventuel « boum » quand le son revient.");
  attendreEntree();
  if (!tunerPret) { dire("  Tuner pas démarré : essai sauté."); resultats[6] = '-'; return; }
  pinMode(BROCHE_AMP_MUTE, OUTPUT);
  digitalWrite(BROCHE_AMP_MUTE, LOW);
  delay(80);                                   // attente avant de rendre le son (conseil du projet Fennec)
  digitalWrite(BROCHE_AMP_MUTE, HIGH);
  dire("  Son rendu.");
  delay(10000);
  digitalWrite(BROCHE_AMP_MUTE, LOW);
  dire("  Son coupé.");
  resultats[6] = reponse("La radio s'est-elle entendue, puis tue ?");
}

// ---------- 8. Bruit de l'ampli en AM
// Le PAM8403 est un ampli de classe D sans filtre : il découpe entre 250 et 450 kHz (350 kHz typique, d'après sa fiche),
// et les multiples de cette fréquence tombent dans la bande AM. On relève la force du signal sur chaque canal AM, son
// du tuner à zéro : ampli muet, puis actif, puis muet encore, pour ne pas confondre avec une station qui varie.
const int NB_CANAUX_AM = 131;                // canaux européens, de 531 à 1701 kHz, tous les 9 kHz
const int HAUSSE_NETTE = 6;                  // en dB : la force du signal double

void releverBandeAM(uint8_t *rssi) {
  for (int i = 0; i < NB_CANAUX_AM; i++) {
    tuner.setFrequency(531 + 9 * i);
    delay(60);
    tuner.getCurrentReceivedSignalQuality();
    rssi[i] = tuner.getCurrentRSSI();
  }
}

void resumerBande(const char *etat, const uint8_t *rssi) {
  long somme = 0;
  int fort = 0;
  for (int i = 0; i < NB_CANAUX_AM; i++) {
    somme += rssi[i];
    if (rssi[i] > rssi[fort]) fort = i;
  }
  Serial.printf("  Ampli %s : bruit moyen %ld dBµV ; le plus fort, %d dBµV à %d kHz.\n",
                etat, somme / NB_CANAUX_AM, rssi[fort], 531 + 9 * fort);
}

void essaiBruitAM() {
  dire("");
  dire("ESSAI 8 SUR 8 : LE BRUIT DE L'AMPLI EN AM. Antenne ferrite sur J3, posée à sa place ; haut-parleurs branchés.");
  dire("  Le programme relève la force du signal sur les 131 canaux AM, son du tuner à zéro : ampli muet, actif, puis muet.");
  dire("  Cela prend environ 40 secondes, et on n'entend rien.");
  dire("  Attendu : aucun canal plus fort de 6 dB quand l'ampli est actif. Sinon, le découpage de l'ampli arrive dans");
  dire("  la radio : voir la fiche de questions, question 6.");
  attendreEntree();
  if (!tunerPret) { dire("  Tuner pas démarré : essai sauté."); resultats[7] = '-'; return; }
  static uint8_t muet1[NB_CANAUX_AM], actif[NB_CANAUX_AM], muet2[NB_CANAUX_AM];
  tuner.setAM(520, 1710, 999, 9);
  tuner.setVolume(0);
  delay(500);
  digitalWrite(BROCHE_AMP_MUTE, LOW);
  delay(200);
  releverBandeAM(muet1);
  digitalWrite(BROCHE_AMP_MUTE, HIGH);
  delay(200);
  releverBandeAM(actif);
  digitalWrite(BROCHE_AMP_MUTE, LOW);
  delay(200);
  releverBandeAM(muet2);
  resumerBande("muet", muet1);
  resumerBande("actif", actif);
  int hausses = 0;
  for (int i = 0; i < NB_CANAUX_AM; i++) {
    int avant = max(muet1[i], muet2[i]);
    if (actif[i] >= avant + HAUSSE_NETTE) {
      Serial.printf("  %d kHz : %d dBµV ampli muet, %d dBµV ampli actif.\n", 531 + 9 * i, avant, actif[i]);
      hausses++;
    }
  }
  Serial.printf("  Canaux plus forts de 6 dB ou plus quand l'ampli est actif : %d sur %d.\n", hausses, NB_CANAUX_AM);
  resultats[7] = hausses ? 'n' : 'o';
  Serial.printf("  Résultat : %s\n", hausses ? "l'ampli gêne l'AM (fiche de questions, question 6)" : "bon");
  tuner.setVolume(40);
  tuner.setFM(8750, 10800, 8750, 10);
}

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);
  pinMode(BROCHE_AMP_MUTE, OUTPUT);
  digitalWrite(BROCHE_AMP_MUTE, LOW);           // ampli muet jusqu'à l'essai 7
  for (int i = 0; i < NB_ESSAIS; i++) resultats[i] = '-';
  delay(500);
  dire("");
  dire("PROGRAMME D'ESSAI DE LA CARTE RADIO RADIONÉO V4.");
  dire("Huit essais, l'un après l'autre. Chacun dit ce qu'il fait et ce qui est attendu.");
  dire("Taper Entrée pour commencer chaque essai ; répondre o ou n aux questions.");
  essaiLED();
  essaiMolette();
  essaiI2C();
  essaiFM();
  essaiAM();
  essaiSon();
  essaiAmpli();
  essaiBruitAM();
  dire("");
  dire("BILAN, à recopier dans le tableau Résultats du plan de test (étape 6) :");
  for (int i = 0; i < NB_ESSAIS; i++)
    Serial.printf("  %s : %s\n", noms[i], resultats[i] == 'o' ? "bon" : resultats[i] == 'n' ? "PAS BON" : "pas fait");
  dire("Fin du programme d'essai. Débrancher la carte.");
}

void loop() { delay(1000); }
