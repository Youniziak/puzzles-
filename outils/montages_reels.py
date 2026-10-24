"""Montages réels : comment d'autres ont branché une puce, d'après des schémas KiCad publiés.
Cherche dans le jeu de données « Open Schematics » (Hugging Face, licence CC-BY 4.0, environ 88 000 schémas) les
schémas qui utilisent une puce, puis, pour chacun, demande à KiCad la liste des liaisons et écrit ce qui est
branché sur chaque broche de la puce (valeurs des condensateurs, résistances, quartz…).
Ce sont des projets publiés, pas des montages vérifiés : ils servent à comparer et à poser de bonnes questions à un
électronicien, pas à prouver qu'un montage marche. Chaque projet garde sa propre licence : on lit et on cite.
Il faut internet (quelques minutes) et la bibliothèque polars ; seules trois colonnes sont lues pour la recherche.
Usage : python3 montages_reels.py 'SI4732' dossier_sortie/            (le motif est une expression régulière,
        sans distinction de majuscules ; plusieurs puces : 'SI4732|PAM8403D')"""
import hashlib, os, re, subprocess, sys, time
import polars as pl

MOTIF, SORTIE = sys.argv[1], sys.argv[2]
JEU = 'hf://datasets/bshada/open-schematics/data/*.parquet'
os.makedirs(os.path.join(SORTIE, 'schemas'), exist_ok=True)
motif_re = re.compile(MOTIF, re.I)
expr = f'(?i){MOTIF}'

t = time.time()
trouves = (pl.scan_parquet(JEU).select(['name', 'description', 'components_used'])
           .filter(pl.col('components_used').list.eval(pl.element().str.contains(expr)).list.any())
           .collect())
depots = sorted(set(trouves['name'].to_list()))
print(f'{len(trouves)} schéma(s) dans {len(depots)} dépôt(s), en {time.time() - t:.0f} s')
schemas = (pl.scan_parquet(JEU).select(['name', 'description', 'schematic', 'components_used', 'extensions_used'])
           .filter(pl.col('name').is_in(depots))
           .filter(pl.col('components_used').list.eval(pl.element().str.contains(expr)).list.any())
           .collect())

def lire(texte):
    jetons = re.findall(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+', texte)
    pile, cour = [], []
    for j in jetons:
        if j == '(':
            pile.append(cour); cour = []
        elif j == ')':
            fini, cour = cour, pile.pop(); cour.append(fini)
        else:
            cour.append(j[1:-1] if j.startswith('"') else j)
    return cour[0]

def champ(e, nom):
    return next((x for x in e if isinstance(x, list) and x and x[0] == nom), None)

rapport, vus = [f'Montages réels de « {MOTIF} » — jeu Open Schematics (https://huggingface.co/datasets/bshada/open-schematics), '
                f'{time.strftime("%d/%m/%Y")}', 'Projets publiés, non vérifiés : à comparer, pas à recopier les yeux fermés.', ''], set()
for r in schemas.iter_rows(named=True):
    texte = r['schematic'] or ''
    empreinte = hashlib.sha1(texte.encode()).hexdigest()[:10]
    if empreinte in vus or not (r['extensions_used'] or [''])[0] == '.kicad_sch':
        continue
    vus.add(empreinte)
    sch = os.path.join(SORTIE, 'schemas', f"{r['name'].replace('/', '__')}-{empreinte}.kicad_sch")
    open(sch, 'w', encoding='utf-8').write(texte)
    net = sch + '.net'
    k = subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '--output', net, sch],
                       capture_output=True, text=True)
    rapport.append(f"== dépôt {r['name']} — {(r['description'] or '').strip()[:100]}")
    if k.returncode or not os.path.exists(net):
        rapport.append('   KiCad ne sait pas en sortir les liaisons (schéma incomplet ou d\'une autre version).'); continue
    arbre = lire(open(net, encoding='utf-8', errors='replace').read())
    valeurs = {}
    for c in champ(arbre, 'components')[1:]:
        ref, val = champ(c, 'ref')[1], (champ(c, 'value') or [None, ''])[1]
        valeurs[ref] = val
    reseaux = [(champ(n, 'name')[1], [(champ(x, 'ref')[1], champ(x, 'pin')[1], (champ(x, 'pinfunction') or [None, ''])[1])
                                       for x in n if isinstance(x, list) and x[0] == 'node'])
               for n in champ(arbre, 'nets')[1:]]
    for puce in [ref for ref, v in valeurs.items() if motif_re.search(v)]:
        rapport.append(f'   {puce} = {valeurs[puce]}')
        broches = []
        for nom, noeuds in reseaux:
            for ref, pin, fonction in noeuds:
                if ref == puce:
                    autres = [f'{r2} {valeurs.get(r2, "?")}' for r2, _, _ in noeuds if r2 != puce]
                    if nom.upper() in ('GND', 'GNDA', 'AGND', 'GNDD'):
                        autres = ['masse']
                    broches.append((int(pin) if pin.isdigit() else 999, pin, fonction.split('_')[0], autres))
        for _, pin, fonction, autres in sorted(broches):
            rapport.append(f'     broche {pin} {fonction} → ' + (', '.join(autres[:6]) or 'non reliée'))
    rapport.append('')
open(os.path.join(SORTIE, 'montages.txt'), 'w', encoding='utf-8').write('\n'.join(rapport))
print('\n'.join(rapport))
