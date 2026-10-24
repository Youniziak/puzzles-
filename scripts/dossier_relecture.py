"""Chaîne puzzle, étape 7 — dossier de relecture : tout ce qu'il faut à un électronicien pour relire une carte,
en un seul zip, avec un mot d'accompagnement. Rien n'est envoyé : le dossier est prêt, la personne l'envoie elle-même.
Dans resultats/NOM/dossier-relecture/ (et dossier-relecture-NOM.zip à côté) :
  00-a-lire-d-abord.pdf (+ .md) : le mot d'accompagnement : le projet, ce qui est demandé, le temps que ça prend,
        ce qui est déjà vérifié (repris de la fiche de questions), la liste des fichiers ;
  01-questions.pdf (+ .md) : la fiche de questions pour l'électronicien (cartes/NOM-questions-electronicien.md) ;
  02-schema.pdf : le schéma ;
  03-carte-couches.pdf : la carte, une couche par page (cuivre dessus et dessous, sérigraphie), par kicad-cli ;
  04-carte-3d.png : l'image 3D du dessus ;
  05-plan-de-test.pdf (+ .md) : le plan de test à la réception (cartes/NOM-plan-de-test.md) ;
  06-controles.txt : les bilans des contrôles de la chaîne (contrôle indépendant, stock, autres fabricants) ;
  kicad/ : le projet KiCad à ouvrir (carte, schéma, règles, empreintes, symboles ; sans les modèles 3D, trop lourds) ;
  fabrication/ : les Gerber, la liste des pièces et le placement.
Les PDF tirés du texte sont balisés (PDF/UA, par pandoc et LibreOffice) : lisibles aussi au lecteur d'écran.
Le texte propre à la carte (auteur, présentation, durée estimée) est dans cartes/NOM.json, rubrique « relecture ».
Usage : python3 dossier_relecture.py cartes/NOM.json resultats/NOM [--kicad-cli kicad-cli]"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, time, zipfile
from xml.sax.saxutils import escape
from description import Carte

p = argparse.ArgumentParser(description="Dossier de relecture pour un électronicien.")
p.add_argument('carte'); p.add_argument('projet')
p.add_argument('--kicad-cli', default='kicad-cli')
a = p.parse_args()
CARTE = Carte(a.carte)
NOM = os.path.splitext(os.path.basename(CARTE.fichier))[0]
CARTES = os.path.dirname(CARTE.fichier)
PROJET = os.path.abspath(a.projet)
SORTIE = os.path.join(PROJET, 'dossier-relecture')
os.makedirs(SORTIE, exist_ok=True)
REL = CARTE.donnees.get('relecture', {})
contenu, manques = [], []          # contenu : (chemin dans le dossier, ce que c'est)
FILTRE_PDF = 'pdf:writer_pdf_Export:' + json.dumps({'UseTaggedPDF': {'type': 'boolean', 'value': 'true'},
                                                     'PDFUACompliance': {'type': 'boolean', 'value': 'true'}})


def pdf_balise(md, pdf):
    """Markdown → PDF balisé (titres, listes, tableaux, langue française, titre du document), par pandoc puis LibreOffice."""
    texte = open(md, encoding='utf-8').read()
    titre = next((l[2:].strip() for l in texte.splitlines() if l.startswith('# ')), os.path.basename(md))
    with tempfile.TemporaryDirectory() as tmp:
        odt, odt2 = os.path.join(tmp, 'a.odt'), os.path.join(tmp, 'doc.odt')
        subprocess.run(['pandoc', md, '-o', odt, '-M', 'lang=fr-FR'], check=True)
        with zipfile.ZipFile(odt) as zin, zipfile.ZipFile(odt2, 'w') as zout:      # titre du document (pandoc le laisse vide)
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == 'meta.xml':
                    data = data.decode('utf-8').replace('<dc:title></dc:title>', f'<dc:title>{escape(titre)}</dc:title>', 1).encode('utf-8')
                zout.writestr(item, data, compress_type=zipfile.ZIP_STORED if item.filename == 'mimetype' else zipfile.ZIP_DEFLATED)
        subprocess.run(['soffice', '--headless', '--convert-to', FILTRE_PDF, '--outdir', tmp, odt2], check=True, capture_output=True)
        shutil.copyfile(os.path.join(tmp, 'doc.pdf'), pdf)


def copier(src, dst_rel, quoi):
    if not os.path.exists(src):
        manques.append(f"{dst_rel} : {os.path.relpath(src, os.path.dirname(CARTES))} introuvable")
        return False
    dst = os.path.join(SORTIE, dst_rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)
    contenu.append((dst_rel, quoi))
    return True


def nombre(v):
    return f"{v:g}".replace('.', ',')


def section(texte, titre):
    """Le texte d'une section « ## titre » d'un fichier markdown (jusqu'à la section suivante)."""
    m = re.search(rf'^## {re.escape(titre)}.*?$\n(.*?)(?=^## |\Z)', texte, re.M | re.S)
    return m.group(1).strip() if m else ''


# ---------- 1. la fiche de questions et le plan de test (texte et PDF balisé)
f_questions = os.path.join(CARTES, f'{NOM}-questions-electronicien.md')
f_test = os.path.join(CARTES, f'{NOM}-plan-de-test.md')
questions = open(f_questions, encoding='utf-8').read() if os.path.exists(f_questions) else ''
n_questions = len(re.findall(r'^### ', questions, re.M))
if questions:
    copier(f_questions, '01-questions.md', 'la fiche de questions, en texte (pour y écrire les réponses)')
    pdf_balise(f_questions, os.path.join(SORTIE, '01-questions.pdf'))
    contenu.append(('01-questions.pdf', f"la fiche de questions ({n_questions} questions), en PDF"))
else:
    manques.append(f"fiche de questions : {os.path.basename(f_questions)} introuvable (à écrire avant d'envoyer le dossier)")

# ---------- 2. schéma, carte couche par couche, image 3D
copier(os.path.join(PROJET, 'schema.pdf'), '02-schema.pdf', 'le schéma (KiCad)')
pcb = os.path.join(PROJET, 'carte.kicad_pcb')
if os.path.exists(pcb):
    sortie_couches = os.path.join(SORTIE, '03-carte-couches.pdf')
    r = subprocess.run([a.kicad_cli, 'pcb', 'export', 'pdf', '--mode-multipage', '--layers', 'F.Cu,B.Cu,F.Silkscreen,B.Silkscreen',
                        '--common-layers', 'Edge.Cuts', '--drill-shape-opt', '2', '--scale', '0', '-o', sortie_couches, pcb],
                       capture_output=True, text=True)
    if r.returncode == 0 and os.path.exists(sortie_couches):
        contenu.append(('03-carte-couches.pdf', 'la carte, une couche par page : cuivre dessus, cuivre dessous, sérigraphie dessus et dessous, avec le contour'))
    else:
        manques.append('carte couche par couche : kicad-cli a échoué (' + ((r.stderr or r.stdout).strip().splitlines() or ['?'])[-1] + ')')
else:
    manques.append('carte.kicad_pcb introuvable : lancer la chaîne avant de faire le dossier')
copier(os.path.join(PROJET, 'image-3d-dessus.png'), '04-carte-3d.png', 'la carte en 3D, vue de dessus')

# ---------- 3. plan de test, bilans des contrôles
if os.path.exists(f_test):
    copier(f_test, '05-plan-de-test.md', 'le plan de test, en texte')
    pdf_balise(f_test, os.path.join(SORTIE, '05-plan-de-test.pdf'))
    contenu.append(('05-plan-de-test.pdf', "le plan de test à la réception de la carte, en PDF"))
bilans = []
for f, titre in (('controle-circuit.txt', 'Contrôle du circuit (noms des broches, découplage, tirages I2C)'),
                 ('controle-independant.txt', 'Contrôle indépendant des fichiers Gerber'),
                 ('disponibilite.txt', 'Stock des pièces'), ('fabricants.txt', 'Autres fabricants')):
    chemin = os.path.join(PROJET, f)
    if os.path.exists(chemin):
        bilans.append(f"===== {titre} ({f}) =====\n\n" + open(chemin, encoding='utf-8').read().strip() + '\n')
if bilans:
    open(os.path.join(SORTIE, '06-controles.txt'), 'w', encoding='utf-8').write('\n\n'.join(bilans))
    contenu.append(('06-controles.txt', 'les bilans des contrôles automatiques de la chaîne'))

# ---------- 4. le projet KiCad (sans les modèles 3D) et les fichiers de fabrication
os.makedirs(os.path.join(SORTIE, 'kicad'), exist_ok=True)
for f in ('carte.kicad_pro', 'carte.kicad_pcb', 'carte.kicad_sch', 'carte.kicad_dru', 'fp-lib-table', 'sym-lib-table'):
    if os.path.exists(os.path.join(PROJET, f)):
        shutil.copyfile(os.path.join(PROJET, f), os.path.join(SORTIE, 'kicad', f))
lib = os.path.join(PROJET, 'lib')
if os.path.isdir(lib):
    for e in sorted(os.listdir(lib)):
        src = os.path.join(lib, e)
        if e.endswith('.pretty'):
            shutil.copytree(src, os.path.join(SORTIE, 'kicad', 'lib', e), dirs_exist_ok=True)
        elif e.endswith('.kicad_sym'):
            os.makedirs(os.path.join(SORTIE, 'kicad', 'lib'), exist_ok=True)
            shutil.copyfile(src, os.path.join(SORTIE, 'kicad', 'lib', e))
if os.path.exists(os.path.join(SORTIE, 'kicad', 'carte.kicad_pro')):
    contenu.append(('kicad/', "le projet KiCad 10 à ouvrir (carte.kicad_pro) : carte, schéma, règles, empreintes et symboles ; "
                              "sans les modèles 3D, trop lourds"))
fab = os.path.join(PROJET, 'fabrication')
for f, quoi in (('gerbers.zip', 'les fichiers Gerber et de perçage'), ('BOM-JLCPCB.csv', 'la liste des pièces (numéros LCSC)'),
                ('CPL-JLCPCB.csv', 'le placement des pièces')):
    copier(os.path.join(fab, f), f'fabrication/{f}', quoi)

# ---------- 4 bis. contrôle électrique de KiCad, avertissements compris (la chaîne ne garde que les erreurs)
erc_texte = ''
sch = os.path.join(SORTIE, 'kicad', 'carte.kicad_sch')
if os.path.exists(sch):
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run([a.kicad_cli, 'sch', 'erc', '--format', 'json', '-o', os.path.join(tmp, 'erc.json'), sch], capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(os.path.join(tmp, 'erc.json')):
            vs = [v for s in json.load(open(os.path.join(tmp, 'erc.json'))).get('sheets', []) for v in s.get('violations', [])]
            err = [v for v in vs if v.get('severity') == 'error']
            avert = [v for v in vs if v.get('severity') != 'error']
            types = {}
            for v in avert:
                types[v.get('type', '?')] = types.get(v.get('type', '?'), 0) + 1
            erc_texte = (f"Le contrôle électrique de KiCad (ERC) trouve {len(err)} erreur(s) et {len(avert)} avertissement(s)"
                         + (" (" + ', '.join(f"{n} « {t} »" for t, n in sorted(types.items(), key=lambda x: -x[1])) + ")" if avert else '') + '.')
            f_off = os.path.join(CARTE.empreintes, 'symboles-officiels.json')
            if os.path.exists(os.path.join(CARTE.empreintes, 'types-broches.json')) and os.path.exists(f_off):
                off = json.load(open(f_off, encoding='utf-8'))['pieces']
                sur_carte = {p.get('lcscPartNumber'): p.get('mpn', '') for b in CARTE.blocs for p in b.design['parts']}
                par_nom = sorted({sur_carte[l] for l, o in off.items() if l in sur_carte and o.get('par') == 'nom' and 'absent' in o.get('note', '')})
                erc_texte += (" Les broches des puces ont le type de la bibliothèque officielle de KiCad (entrée, sortie, alimentation…), "
                              "ce qui permet à ce contrôle de voir une sortie contre une sortie ou une alimentation non fournie"
                              + (f" ; pour {', '.join(par_nom)}, absent de cette bibliothèque, les types sont repris d'une puce de la même famille, "
                                 "en rapprochant les noms des broches : à confirmer avec sa fiche" if par_nom else '') + '.')
            if any('Unspecified' in it.get('description', '') for v in avert for it in v.get('items', [])):
                erc_texte += (" Les symboles téléchargés (easyeda2kicad) ne disent pas le type de la plupart de leurs broches "
                              "(« Unspecified ») : KiCad ne peut donc pas vérifier, par exemple, que deux sorties ne sont pas reliées "
                              "entre elles. Ce contrôle-là reste à faire à l'œil.")

# ---------- 5. le mot d'accompagnement
blocs = [(b.bloc.get('etiquette', b.id), b.bloc.get('description', '')) for b in CARTE.blocs]
n_comp = sum(len([p for p in b.design['parts'] if p['id'] not in b.bloc.get('non_poses', [])]) for b in CARTE.blocs)
confiance = next((re.sub(r'\*+', '', l).strip() for l in questions.splitlines() if 'Niveau de confiance' in l), '')
deja = section(questions, 'Ce que la chaîne a déjà vérifié')
fabricant = CARTE.regles.get('nom', CARTE.nom_regles)
lignes = [f"# Relecture de la carte « {CARTE.nom} »", '',
          f"{REL.get('auteur', '')} — {time.strftime('%d/%m/%Y')}".strip(' —'), '']
if REL.get('presentation'):
    lignes += [REL['presentation'], '']
lignes += ["## Ce que je vous demande", '',
           f"Répondre aux {n_questions} questions de la fiche (01-questions.pdf) : elles portent sur ce que les outils automatiques "
           "ne savent pas juger. Pas besoin de tout relire : le reste est déjà vérifié (voir plus bas)."
           + (f" Temps estimé : {REL['duree_estimee']}." if REL.get('duree_estimee') else ''), '',
           "Vous pouvez répondre comme vous préférez : dans la fiche (en PDF annoté, ou dans le fichier texte 01-questions.md), "
           "par courriel, ou de vive voix. Une réponse partielle m'aide déjà beaucoup.", '',
           "## La carte en bref", '',
           f"- {nombre(CARTE.largeur)} × {nombre(CARTE.hauteur)} mm, 2 couches, prévue pour : {fabricant}.",
           f"- {n_comp} composants, en {len(blocs)} blocs :"]
lignes += [f"  - {et} : {desc}" for et, desc in blocs]
if confiance:
    lignes += [f"- {confiance}"]
lignes += ['', "## Comment elle a été faite", '',
           "Chaque bloc a été routé par EasyGerber, puis les blocs ont été assemblés et contrôlés avec des logiciels libres : "
           "KiCad 10, Freerouting et KiKit, plus un contrôle indépendant des fichiers Gerber. "
           "Je conçois mes cartes sans la vue : un regard humain du métier est l'étape qui manque.", '']
if deja:
    lignes += ["## Ce qui est déjà vérifié (inutile d'y passer du temps)", '', deja, '']
if erc_texte:
    lignes += ["## Le contrôle électrique", '', erc_texte, '']
lignes += ["## Les fichiers du dossier", '']
lignes += [f"- {c} : {q}." for c, q in contenu if not c.endswith('.md')]
lignes += [f"- {c} : {q}." for c, q in contenu if c.endswith('.md')]
lignes += ['', "Merci d'avance pour votre temps."]
md0 = os.path.join(SORTIE, '00-a-lire-d-abord.md')
open(md0, 'w', encoding='utf-8').write('\n'.join(lignes) + '\n')
pdf_balise(md0, os.path.join(SORTIE, '00-a-lire-d-abord.pdf'))
contenu[:0] = [('00-a-lire-d-abord.pdf', "le mot d'accompagnement"), ('00-a-lire-d-abord.md', "le même, en texte")]

# ---------- 6. le zip (seulement les fichiers de ce passage), et le bilan
zip_chemin = os.path.join(PROJET, f'dossier-relecture-{NOM}.zip')
racine = f'dossier-relecture-{NOM}'
with zipfile.ZipFile(zip_chemin, 'w', zipfile.ZIP_DEFLATED) as z:
    for rel, _ in contenu:
        src = os.path.join(SORTIE, rel)
        if os.path.isdir(src):
            for r, _, fs in os.walk(src):
                for f in sorted(fs):
                    z.write(os.path.join(r, f), os.path.join(racine, os.path.relpath(os.path.join(r, f), SORTIE)))
        else:
            z.write(src, os.path.join(racine, rel))
taille = os.path.getsize(zip_chemin) / 1e6
print(f"Dossier de relecture : {SORTIE}")
print(f"Zip à envoyer : {zip_chemin} ({nombre(round(taille, 1))} Mo)")
for c, q in contenu:
    print(f"  ✓ {c} : {q}")
for m in manques:
    print(f"  ✗ manque : {m}")
if taille > 20:
    print("  ⚠ plus de 20 Mo : trop gros pour certaines messageries ; passer par un lien de partage")
sys.exit(1 if manques else 0)
