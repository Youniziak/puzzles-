#!/bin/bash
# Installe les logiciels de la chaîne puzzle sur Ubuntu 24.04 : les mêmes versions que celles essayées le 22/10/2026.
#   KiCad 10 (dépôt officiel de KiCad), Java 21 et Freerouting 2.1.0, ngspice,
#   OpenSCAD et YAPP_Box 3.3.8 (boîtiers),
#   et, dans un environnement Python à part : KiKit 1.8.1, gerbonara, shapely, CadQuery, easyeda2kicad, trimesh,
#   pyflakes (relit les scripts de la chaîne avant de la lancer).
# Usage : bash installer-ubuntu.sh [dossier des outils]      (par défaut : ~/chaine-puzzle-outils)
# À la fin, le script affiche la commande pour lancer la chaîne.
# Note honnête : ce script reprend pas à pas l'installation faite à la main le 22/10/2026, mais il n'a pas encore
# été lancé tel quel sur une machine neuve. S'il s'arrête, le message dit à quelle étape.
set -euo pipefail

OUTILS="${1:-$HOME/chaine-puzzle-outils}"
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
FREEROUTING_URL="https://github.com/freerouting/freerouting/releases/download/v2.1.0/freerouting-2.1.0.jar"
YAPP_COMMIT="f9400c419ef1dea7dc0b3607876989b4f3faa2b7"   # YAPP_Box 3.3.8 (24/08/2025), essayé le 23/10/2026
FREEROUTING_SHA256="2c07d58f75dac03782664081e7a58b41c25400d871a9fcf166a2ea6fe60d5def"   # le fichier essayé le 22/10/2026

etape() { echo; echo "=== $* ==="; }
trap 'echo; echo "ÉCHEC pendant l étape ci-dessus."' ERR

etape "1/5 Dépôt officiel de KiCad 10"
$SUDO apt-get update
$SUDO apt-get install -y --no-install-recommends software-properties-common ca-certificates curl gpg-agent git
$SUDO add-apt-repository -y ppa:kicad/kicad-10.0-releases
$SUDO apt-get update

etape "2/5 KiCad 10, Java 21, Python, ngspice"
$SUDO apt-get install -y --no-install-recommends kicad openjdk-21-jre-headless python3-venv python3-pip python3-wxgtk4.0 ngspice fonts-dejavu-core \
    liblouis-bin python3-louis sigrok-cli pandoc libreoffice-writer
kicad-cli version

etape "3/5 Freerouting 2.1.0"
mkdir -p "$OUTILS"
curl -fL -o "$OUTILS/freerouting-2.1.0.jar" "$FREEROUTING_URL"
echo "$FREEROUTING_SHA256  $OUTILS/freerouting-2.1.0.jar" | sha256sum -c -

etape "4/5 Bibliothèques Python (environnement à part, qui voit le module pcbnew de KiCad)"
python3 -m venv --system-site-packages "$OUTILS/venv"
"$OUTILS/venv/bin/pip" install --upgrade pip
"$OUTILS/venv/bin/pip" install kikit==1.8.1 gerbonara==1.6.3 shapely==2.2.0 cadquery==2.8.0 easyeda2kicad==1.0.1 polars==2.0.0 \
    matplotlib==3.11.2 trimesh==5.1.1 rtree==1.4.1 scipy==1.18.1 platformio==6.1.18 pyflakes==4.0.3
"$OUTILS/venv/bin/python" -c "import pcbnew, kikit, gerbonara, shapely, cadquery, polars, matplotlib, trimesh, rtree, scipy, louis, pyflakes; print('modules Python : tout est là')"

etape "5/5 Boîtiers : OpenSCAD et YAPP_Box 3.3.8 (licence MIT)"
$SUDO apt-get install -y --no-install-recommends openscad
openscad --version
[ -d "$OUTILS/YAPP_Box/.git" ] || git clone https://github.com/mrWheel/YAPP_Box "$OUTILS/YAPP_Box"
git -C "$OUTILS/YAPP_Box" checkout --quiet "$YAPP_COMMIT"
ls "$OUTILS/YAPP_Box/YAPPgenerator_v3.scad"

echo
echo "Installation terminée. Pour lancer la chaîne, depuis le dossier de la chaîne :"
echo "  $OUTILS/venv/bin/python scripts/chaine.py cartes/radio-v3.json resultats/radio-v3 \\"
echo "      --freerouting $OUTILS/freerouting-2.1.0.jar --kikit $OUTILS/venv/bin/kikit --yapp $OUTILS/YAPP_Box"
