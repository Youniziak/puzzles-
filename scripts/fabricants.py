"""Chaîne puzzle, étape 3 quater — « autres fabricants » : la même carte peut-elle partir chez un autre fabricant ?
Pour chaque fichier de règles de fabricant (bibliotheque/regles/*.json avec "type": "fabricant") :
  1. KiCad 10 contrôle la carte avec les règles de ce fabricant, sur une copie du projet dont les plans de cuivre
     sont refaits avec ces règles (rien n'est changé à la carte elle-même) ;
  2. KiCad sort les fichiers Gerber de cette copie, et le contrôle indépendant les relit avec les mêmes règles ;
  3. si tout passe et que KiKit connaît ce fabricant, KiKit prépare ses fichiers (Gerber, et liste des pièces
     et placement pour l'assemblage, à partir du schéma) ;
  4. un résumé : fabricants.txt, dans le dossier du projet.
La carte reste routée pour le fabricant de sa description (« regles ») : ce contrôle dit seulement si elle convient
aussi ailleurs, et sinon pourquoi.
Usage : python3 fabricants.py cartes/ma-carte.json dossier_projet/carte.kicad_pcb chemin/kikit"""
import json, math, os, re, shutil, subprocess, sys
import pcbnew
from collections import defaultdict
from description import Carte

CARTE = Carte(sys.argv[1])
PCB, KIKIT = os.path.abspath(sys.argv[2]), sys.argv[3]
PROJET = os.path.dirname(PCB)
BASE = PCB[:-len('.kicad_pcb')]
ICI = os.path.dirname(os.path.abspath(__file__))
DOSSIER_REGLES = os.path.join(CARTE.bibliotheque, 'regles')
SORTIE = os.path.join(PROJET, 'fabricants')
os.makedirs(SORTIE, exist_ok=True)

NOMS = {'clearance': 'écart entre cuivres', 'annular_width': 'couronne de cuivre autour d\'un trou',
        'drill_out_of_range': 'diamètre de trou', 'hole_clearance': 'écart entre un trou et le cuivre',
        'hole_to_hole': 'écart entre deux trous', 'copper_edge_clearance': 'cuivre trop près du bord',
        'track_width': 'largeur de piste', 'via_diameter': 'diamètre de via', 'hole_size': 'diamètre de trou'}

fabricants = []
for f in sorted(os.listdir(DOSSIER_REGLES)):
    if f.endswith('.json'):
        r = json.load(open(os.path.join(DOSSIER_REGLES, f), encoding='utf-8'))
        if r.get('type') == 'fabricant':
            fabricants.append((f[:-5], r))
fabricants.sort(key=lambda x: x[0] != CARTE.nom_regles)          # celui de la carte d'abord

non_poses = sorted({CARTE.repere(b, x) for b in CARTE.blocs for x in b.bloc.get('non_poses', [])})
resume = []
for nom, R in fabricants:
    d = os.path.join(SORTIE, nom)
    os.makedirs(d, exist_ok=True)
    # 1. KiCad, avec les règles de ce fabricant, sur une copie
    copie = os.path.join(d, 'carte.kicad_pcb')
    shutil.copy2(PCB, copie)
    pro = json.load(open(BASE + '.kicad_pro'))
    pro.setdefault('board', {}).setdefault('design_settings', {}).setdefault('rules', {}).update(R['kicad'])
    json.dump(pro, open(os.path.join(d, 'carte.kicad_pro'), 'w'), indent=2)
    seuil = R['controle']['trou_metallise_cuivre'] - 0.005
    regles = [f'(rule "trou metallise - cuivre (fabricant)" (constraint hole_clearance (min {seuil:.3f}mm)) (condition "A.isPlated()"))']
    regles += R.get('regles_kicad_dru', [])
    open(os.path.join(d, 'carte.kicad_dru'), 'w').write('(version 1)\n' + '\n'.join(regles) + '\n')
    principal = nom == CARTE.nom_regles
    # Ajustement permis par le fichier de règles : agrandir les vias dont la couronne est trop fine pour ce fabricant
    # (sur la copie seulement ; KiCad et le contrôle indépendant vérifient ensuite que les écarts restent bons).
    ajustes = 0
    if not principal and R.get('ajustements', {}).get('agrandir_vias'):
        b = pcbnew.LoadBoard(copie)
        c_min = R['kicad']['min_via_annular_width']
        for v in b.GetTracks():
            if v.GetClass() == 'PCB_VIA':
                dia, trou = pcbnew.ToMM(v.GetWidth(pcbnew.F_Cu)), pcbnew.ToMM(v.GetDrillValue())
                if (dia - trou) / 2 < c_min - 1e-6:
                    v.SetWidth(pcbnew.FromMM(math.ceil((trou + 2 * c_min) * 100 - 1e-6) / 100))
                    ajustes += 1
        pcbnew.SaveBoard(copie, b)
    # Les sorties en cuivre nu ne se posent pas : hors liste des pièces et placement (cartes faites avant cette règle)
    b = pcbnew.LoadBoard(copie)
    for fp in b.GetFootprints():
        if fp.GetReference() in non_poses:
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM)
    pcbnew.SaveBoard(copie, b)
    rapport = os.path.join(d, 'controle-kicad.json')
    cmd = ['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-error', '--output', rapport]
    if not principal:
        cmd += ['--refill-zones', '--save-board']       # plans de cuivre refaits avec les écarts de ce fabricant
    subprocess.run(cmd + [copie], capture_output=True, check=True)
    drc = json.load(open(rapport))
    par_type = defaultdict(list)
    for v in drc['violations']:
        par_type[v['type']].append(v)
    # 2. Contrôle indépendant des fichiers Gerber, avec les mêmes règles
    if principal:
        texte = open(os.path.join(PROJET, 'controle-independant.txt'), encoding='utf-8').read()
    else:
        gerber = os.path.join(d, 'gerber') + os.sep
        shutil.rmtree(gerber, ignore_errors=True); os.makedirs(gerber)
        subprocess.run(['kicad-cli', 'pcb', 'export', 'gerbers', '--output', gerber, copie], capture_output=True, check=True)
        subprocess.run(['kicad-cli', 'pcb', 'export', 'drill', '--excellon-separate-th', '--output', gerber, copie],
                       capture_output=True, check=True)
        rv = subprocess.run([sys.executable, '-I', os.path.join(ICI, 'verif_gerber.py'), CARTE.fichier, gerber, nom],
                            capture_output=True, text=True)
        texte = rv.stdout + rv.stderr
        open(os.path.join(d, 'controle-independant.txt'), 'w', encoding='utf-8').write(texte)
    bilan = texte.split('== Bilan ==')[-1].strip().splitlines() if '== Bilan ==' in texte else ['bilan introuvable']
    independant_ok = any('rien à corriger' in l for l in bilan)
    conforme = not drc['violations'] and not drc.get('unconnected_items') and independant_ok
    # 3. Fichiers du fabricant
    fichiers = ''
    if conforme and principal:
        fichiers = 'fichiers dans fabrication/ (Gerber de KiKit, liste des pièces et placement repris d\'EasyGerber)'
    elif conforme and R.get('kikit'):
        sortie_k = os.path.join(d, 'fabrication')
        cmd = [KIKIT, 'fab', R['kikit'], '--no-drc', '--assembly', '--schematic', BASE + '.kicad_sch',
               '--manufacturer', 'Manufacturer', '--partNumber', 'MPN', copie, sortie_k]
        rk = subprocess.run(cmd, capture_output=True, text=True)
        if rk.returncode == 0:
            fichiers = f"fichiers préparés par KiKit dans fabricants/{nom}/fabrication/ : " + ', '.join(sorted(os.listdir(sortie_k)))
        else:
            fichiers = 'KiKit a échoué : ' + [l for l in (rk.stdout + rk.stderr).splitlines() if l.strip()][-1]
    elif conforme:
        fichiers = f'pas de préréglage KiKit : envoyer les Gerber et perçages de fabricants/{nom}/gerber/ (sortis par KiCad)'
    raisons = []
    for t, vs in sorted(par_type.items(), key=lambda x: -len(x[1])):
        raisons.append(f"{len(vs)} × {NOMS.get(t, t)} — exemple : {vs[0]['description']} "
                       f"({', '.join(i['description'] for i in vs[0]['items'][:2])})")
    if not independant_ok:
        raisons += ['contrôle indépendant : ' + l.strip() for l in bilan if l.strip()]
    resume.append((nom, R, conforme, raisons, fichiers, ajustes))

lignes = [f"Autres fabricants — {CARTE.nom}", '',
          f"La carte est routée pour « {CARTE.regles['nom']} ». Ci-dessous : convient-elle aussi ailleurs ?", '']
for nom, R, conforme, raisons, fichiers, ajustes in resume:
    lignes.append(f"{'✓' if conforme else '✗'} {R['nom']}" + (' (fabricant de la carte)' if nom == CARTE.nom_regles else ''))
    lignes.append(f"    source des règles : {R.get('source', '?')}")
    if ajustes:
        lignes.append(f"    ajusté pour ce fabricant : {ajustes} via(s) agrandi(s), pour une couronne de "
                      f"{str(R['kicad']['min_via_annular_width']).replace('.', ',')} mm (dans fabricants/{nom}/ seulement ; la carte d'origine n'est pas changée)")
    if conforme:
        lignes.append('    conforme : KiCad et le contrôle indépendant ne trouvent rien.')
        lignes.append('    ' + fichiers)
    else:
        lignes.append('    pas conforme tel quel :')
        lignes += ['      - ' + r for r in raisons[:8]]
    lignes.append('    stock des pièces : ' + ('vérifiable avec --disponibilite' if R.get('stock_verifiable')
                                                else (R.get('notes', {}).get('assemblage') or 'pas vérifiable d\'ici : voir le devis du fabricant')))
    lignes.append('')
open(os.path.join(PROJET, 'fabricants.txt'), 'w', encoding='utf-8').write('\n'.join(lignes))
print('\n'.join(lignes))
