# Chaîne puzzle dans un conteneur : les mêmes logiciels partout (ordinateur, serveur, FabLab).
# Construire :  docker build -t chaine-puzzle .
# Lancer     :  docker run --rm -v "$PWD/resultats:/chaine/resultats" chaine-puzzle cartes/radio-v3.json resultats/radio-v3
#               (les résultats arrivent dans le dossier resultats/ de l'ordinateur)
# Pour une nouvelle carte : ajouter son fichier dans cartes/ (et ses blocs dans bibliotheque/), puis reconstruire.
ARG BASE=ubuntu:24.04
FROM ${BASE}
ENV DEBIAN_FRONTEND=noninteractive
COPY installer-ubuntu.sh /tmp/installer-ubuntu.sh
RUN bash /tmp/installer-ubuntu.sh /opt/outils && rm -rf /var/lib/apt/lists/* /root/.cache/pip
COPY scripts /chaine/scripts
COPY outils /chaine/outils
COPY bibliotheque /chaine/bibliotheque
COPY cartes /chaine/cartes
WORKDIR /chaine
# Bibliothèque des composants de LCSC/EasyEDA : pas dans le dépôt (conditions d'EasyEDA), téléchargée à la construction.
# (Code 3 : LCSC a changé une pièce depuis ; la bibliothèque est rangée quand même, et le message dit laquelle relire.)
RUN /opt/outils/venv/bin/python outils/telecharger_bibliotheque.py --easyeda2kicad /opt/outils/venv/bin/easyeda2kicad || [ $? -eq 3 ]
ENTRYPOINT ["/opt/outils/venv/bin/python", "scripts/chaine.py", "--freerouting", "/opt/outils/freerouting-2.1.0.jar", "--kikit", "/opt/outils/venv/bin/kikit", "--yapp", "/opt/outils/YAPP_Box"]
