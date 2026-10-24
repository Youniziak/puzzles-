"""Chaîne puzzle, étape 3 — « fabrication ».
- Fichiers Gerber et perçages : KiKit (libre).
- Liste des composants (BOM) : fusion de celles d'EasyGerber, bloc par bloc, avec les repères de la carte.
- Placement (CPL) : positions et rotations d'EasyGerber, ramenées à la place du bloc sur la carte.
  Les composants « non posés » d'un bloc (pastilles de sortie en cuivre nu) sont hors BOM et placement.
- Image 3D de la carte : KiCad 10.
- Contrôle indépendant des fichiers Gerber (verif_gerber.py), sans passer par KiCad.
Usage : python3 fab.py cartes/ma-carte.json dossier_projet/carte.kicad_pcb chemin/kikit"""
import csv, os, subprocess, sys
from description import Carte

CARTE = Carte(sys.argv[1])
PCB, KIKIT = sys.argv[2], sys.argv[3]
PROJET = os.path.dirname(os.path.abspath(PCB))
FAB = os.path.join(PROJET, 'fabrication')
os.makedirs(FAB, exist_ok=True)

subprocess.run([KIKIT, 'fab', 'jlcpcb', '--no-drc', PCB, FAB], capture_output=True, check=True)
print('Gerber (KiKit) :', os.path.join(FAB, 'gerbers.zip'))

bom, cpl = {}, []
for b in CARTE.blocs:
    non_poses = set(b.bloc.get('non_poses', []))
    for r in csv.DictReader(open(os.path.join(b.easygerber, 'BOM.csv'), encoding='utf-8')):
        reperes = [x.strip() for x in r['Designator'].split(',') if x.strip() not in non_poses]
        if not reperes:
            continue
        reperes = ', '.join(CARTE.repere(b, x) for x in reperes)
        cle = r['LCSC Part #'] or r['MPN'] or r['Comment']
        if cle in bom:
            bom[cle]['Designator'] += ', ' + reperes
        else:
            bom[cle] = dict(r, Designator=reperes)
    for p in b.design['parts']:
        if p['id'] in non_poses:
            continue
        x, y = b.point(p['x'], p['y'])
        cpl.append({'Designator': CARTE.repere(b, p['id']), 'Mid X': f'{x:.4f}mm', 'Mid Y': f'{y:.4f}mm',
                    'Rotation': f'{b.angle(p["rotation"]):.1f}', 'Layer': 'Top' if p.get('layer', 'top') == 'top' else 'Bottom'})
with open(os.path.join(FAB, 'BOM-JLCPCB.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(next(iter(bom.values())).keys()), quoting=csv.QUOTE_ALL); w.writeheader(); w.writerows(bom.values())
with open(os.path.join(FAB, 'CPL-JLCPCB.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['Designator', 'Mid X', 'Mid Y', 'Rotation', 'Layer'], quoting=csv.QUOTE_ALL); w.writeheader(); w.writerows(cpl)
print(f'BOM : {len(bom)} lignes ; placement : {len(cpl)} composants')

subprocess.run(['kicad-cli', 'pcb', 'render', '--side', 'top', '--width', '1800', '--height', '1500', '--quality', 'high',
                '--output', os.path.join(PROJET, 'image-3d-dessus.png'), PCB], capture_output=True, check=True)
print('Image 3D :', os.path.join(PROJET, 'image-3d-dessus.png'))

ICI = os.path.dirname(os.path.abspath(__file__))
r = subprocess.run([sys.executable, '-I', os.path.join(ICI, 'verif_gerber.py'), CARTE.fichier, os.path.join(FAB, 'gerber')],
                   capture_output=True, text=True)
open(os.path.join(PROJET, 'controle-independant.txt'), 'w').write(r.stdout + r.stderr)
print(r.stdout + r.stderr)
sys.exit(r.returncode)
