"""Chaîne puzzle, avant tout : relire les scripts de la chaîne eux-mêmes, en une seconde, avant d'y passer vingt minutes.
Il cherche les erreurs qui feraient planter une étape en route :
  - une erreur de syntaxe (Python lui-même : compile) ;
  - un nom inconnu, par exemple une variable renommée à un endroit et pas à l'autre (pyflakes, paquet python3-pyflakes).
Constaté le 24/10/2026 : en passant la maquette à liblouis, une ligne parlait encore de l'ancienne table « BRAILLE ».
L'étape 4 plantait au bout d'une minute, et rien ne l'avait vu avant.
Usage : python3 relire_scripts.py    (code de sortie 1 s'il y a une erreur)"""
import glob, os, re, subprocess, sys

ICI = os.path.dirname(os.path.abspath(__file__))
fichiers = sorted(glob.glob(os.path.join(ICI, '*.py')) + glob.glob(os.path.join(ICI, '..', 'outils', '*.py')))
racine = os.path.dirname(ICI)
nom = lambda f: os.path.relpath(f, racine)

erreurs = []
for f in fichiers:
    try:
        compile(open(f, encoding='utf-8').read(), f, 'exec')
    except SyntaxError as e:
        erreurs.append(f"{nom(f)}, ligne {e.lineno} : erreur de syntaxe ({e.msg})")

r = subprocess.run([sys.executable, '-m', 'pyflakes', *fichiers], capture_output=True, text=True)
if 'No module named pyflakes' in r.stderr:
    note = "pyflakes absent (paquet python3-pyflakes) : les noms inconnus ne sont pas cherchés."
else:
    for ligne in r.stdout.splitlines():
        m = re.match(r"^(.*?):(\d+):(?:\d+:)? undefined name '(.+)'", ligne)
        if m:
            erreurs.append(f"{nom(m.group(1))}, ligne {m.group(2)} : nom inconnu « {m.group(3)} » : l'étape planterait en arrivant là")
    note = "noms inconnus cherchés avec pyflakes."

print(f"{len(fichiers)} scripts relus ; {note}")
for e in erreurs:
    print(f"✗ {e}")
print("Bilan : " + (f"{len(erreurs)} erreur(s) à corriger avant de lancer la chaîne." if erreurs else "aucune erreur."))
sys.exit(1 if erreurs else 0)
