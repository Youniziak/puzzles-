"""Chercher par fonction : quels projets publiés font telle chose, avec quelles pièces, et quels pièges sont connus.

1. Projets : dans l'index d'Open Schematics (88 000 schémas de 30 000 dépôts GitHub), le motif est cherché dans la
   description de chaque dépôt (écrite par son auteur, en général en anglais : chercher en anglais) et dans son nom.
   Le rapport donne d'abord les pièces qui reviennent chez le plus d'auteurs différents (sans les résistances,
   condensateurs, connecteurs, symboles d'alimentation…) : ce qu'on prend d'habitude pour cette fonction. Puis,
   pour chaque dépôt, son lien, sa description et ses pièces principales. Pour voir comment une de ces pièces est
   branchée : outils/montages_reels.py.
2. Pièges (--pieges) : dans une copie des questions d'Electronics Stack Exchange (95 000 questions avec une réponse,
   de 2009 à mars 2024), les questions dont le titre, le texte ou les étiquettes portent le motif. Pour chacune : le
   lien, la date, les étiquettes, le début de la question et de la réponse gardée par le jeu (on ne sait pas si
   c'est la réponse acceptée). Une réponse de forum n'est pas une preuve : certaines sont fausses. Les titres des
   questions disent déjà où les autres se sont trompés. Licence CC BY-SA : chaque question est citée avec son lien,
   ses auteurs sont nommés sur sa page.

On lit et on cite : chaque projet garde sa licence, rien n'est recopié dans le dépôt. Il faut internet la première
fois (index d'Open Schematics, environ 3 minutes ; 130 Mo pour Electronics Stack Exchange) et polars.
Usage : python3 outils/chercher_fonction.py 'FM radio|AM radio' dossier/ [--composant 'SI47'] [--pieges 'SI473']
                                                                        [--max 30]
        Les motifs sont des expressions régulières simples, sans distinction de majuscules. Motif « - » : pas de
        recherche de projets (seulement les pièges)."""
import argparse, html, os, re, sys, time
from collections import defaultdict
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jeux_donnees import JEUX, telecharger, depot_de, index_open_schematics

ap = argparse.ArgumentParser(description='Projets publiés qui font telle chose, et pièges connus.')
ap.add_argument('motif', help="ce que fait la carte, en anglais ('FM radio|AM radio') ; « - » pour sauter")
ap.add_argument('sortie')
ap.add_argument('--composant', help="ne garder que les projets qui ont une pièce de ce nom ('SI47|RDA5807')")
ap.add_argument('--pieges', help="chercher aussi les questions d'Electronics Stack Exchange qui en parlent ('PAM8403')")
ap.add_argument('--max', type=int, default=30, help='dépôts et questions au plus (30 par défaut)')
A = ap.parse_args()
os.makedirs(A.sortie, exist_ok=True)

# symboles sans intérêt pour savoir « avec quoi c'est fait » : composants de base, connecteurs, alimentations, logos
GENERIQUE = re.compile(
    r'^(R|C|L|D|CP|LED|Q|RN|Crystal|Resonator|Fuse|Polyfuse|Ferrite|FerriteBead|Battery|Buzzer|Speaker|Thermistor|'
    r'Varistor|Jumper|SolderJumper|NetTie|Net-Tie|TestPoint|MountingHole|Fiducial|Conn|Screw_Terminal|USB|SW|Switch|'
    r'Antenna|Logo|LOGO|Graphic|Opamp_Dual|R_POT|Hole|Pin|Header|Barrel_Jack|AudioJack\w*)(_.*)?$'
    r'|^[+-]|^(GND\w*|VCC|VDD|VSS|VBUS|VBAT|VIN|PWR_FLAG|Earth\w*|\w+_Small)$'
    r'|^(0201|0402|0603|0805|1206|1210|2512)\b|\d\s*(Ω|[kKM]Ω|[munpµ]F|[munµ]H)\b|ohm', re.I)


def normaliser(c):
    """« NPN,MMBT2222A » → « MMBT2222A » ; les noms décrits à la mode JLCPCB (« Crystal, 32.768kHz, 13pF »,
    « LED,0805,Green ») sont des composants de base : rendus vides."""
    if ',' not in c:
        return c.strip()
    tete, reste = c.split(',', 1)
    if re.search(r'\d', tete) and re.search(r'[A-Za-z]', tete):
        return c.strip()                    # « TDA1517P/N3,112 » : vraie référence avec une virgule
    if re.fullmatch(r'(?i)\s*(NPN|PNP|General|Diode|Schottky|Zener|MOSFET|N-?MOS|P-?MOS|IC|TVS)\s*', tete):
        return reste.split(',')[0].strip()
    return ''


def principales(composants):
    return sorted({n for n in map(normaliser, composants or []) if n and not GENERIQUE.match(n) and re.search(r'\d', n)})


def texte_brut(h, n):
    t = ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', h or '')).split())
    return t if len(t) <= n else t[:n].rsplit(' ', 1)[0] + '…'


rapport = [f'Recherche par fonction — {time.strftime("%d/%m/%Y")}', '']

if A.motif != '-':
    expr = f'(?i){A.motif}'
    idx = pl.read_parquet(index_open_schematics())
    t = idx.filter(pl.col('description').fill_null('').str.contains(expr) | pl.col('name').str.contains(expr))
    if A.composant:
        t = t.filter(pl.col('components_used').list.eval(pl.element().str.contains(f'(?i){A.composant}')).list.any())
    par_depot = defaultdict(lambda: {'nom': '', 'desc': '', 'pieces': set(), 'formats': set()})
    for nom, desc, comps, ext in t.select(['name', 'description', 'components_used', 'extensions_used']).iter_rows():
        d = par_depot[depot_de(nom)]
        d['nom'], d['desc'] = nom, d['desc'] or ' '.join((desc or '').split())
        d['pieces'].update(principales(comps))
        d['formats'].update(e for e in ext or [] if e != '.kicad_pcb')
    auteurs_de = defaultdict(set)      # pièce → auteurs
    for depot, d in par_depot.items():
        for p in d['pieces']:
            auteurs_de[p].add(depot.split('/')[0])
    auteurs = {depot.split('/')[0] for depot in par_depot}
    communes = sorted(((p, len(a)) for p, a in auteurs_de.items() if len(a) >= 2), key=lambda x: (-x[1], x[0]))
    rapport += [f'Projets dont la description ou le nom porte « {A.motif} »'
                + (f', avec une pièce « {A.composant} »' if A.composant else '') + ' :',
                f'  {len(t)} schéma(s) dans {len(par_depot)} dépôt(s), de {len(auteurs)} auteur(s) — source : '
                f'{JEUX["open-schematics"]["nom"]}, {JEUX["open-schematics"]["page"]}',
                "  Les descriptions sont celles des auteurs, recopiées telles quelles. Chaque projet garde sa licence.", '',
                "Pièces qui reviennent chez au moins deux auteurs (sans les résistances, condensateurs, connecteurs…) :",
                *([f'  {p} : {n} auteurs' for p, n in communes[:25]] or ['  aucune.']),
                "Vues chez un seul auteur (pistes à regarder) : "
                + ('; '.join(sorted(p for p, a in auteurs_de.items() if len(a) == 1)[:60]) or 'aucune.'),
                "  (Open Schematics ne liste les pièces que pour les schémas KiCad 6 et plus : pour les autres, ouvrir le dépôt.)",
                '',
                f'Les dépôts (au plus {A.max}, ceux qui ont le plus de pièces communes d\'abord) :', '']
    poids = {p: n for p, n in communes}
    for depot, d in sorted(par_depot.items(), key=lambda x: (-sum(poids.get(p, 0) for p in x[1]['pieces']), x[0]))[:A.max]:
        rapport += [f"== {d['nom']} — https://github.com/{d['nom']}",
                    f"   « {d['desc'][:200]}{'…' if len(d['desc']) > 200 else ''} »" if d['desc'] else '   (pas de description)',
                    '   pièces principales : ' + ('; '.join(sorted(d['pieces'], key=lambda p: (-poids.get(p, 0), p))[:12])
                                                 or ('non listées par le jeu (schéma ' + ', '.join(sorted(d['formats'] - {'.kicad_sch'}))
                                                     + ')' if d['formats'] - {'.kicad_sch'} else 'aucune hors composants de base')),
                    '']

if A.pieges:
    J = JEUX['electronics-se']
    expr = f'(?i){A.pieges}'
    q = (pl.scan_parquet(telecharger(J['index'], 'electronics-se/questions.parquet'))
         .filter(pl.col('Title').str.contains(expr) | pl.col('Tags').str.contains(expr) | pl.col('Body').str.contains(expr))
         .with_columns(pl.col('Title').str.contains(expr).alias('dans_titre'))
         .sort(['dans_titre', 'CreationDate'], descending=[True, True]).collect())
    rapport += [f"Pièges connus : questions d'Electronics Stack Exchange qui parlent de « {A.pieges} » — {len(q)} question(s)"
                + (f', les {A.max} premières' if len(q) > A.max else '') + " (titre d'abord, puis les plus récentes)",
                f"  Source : {J['nom']}, copie {J['page']}. Licence {J['licence']}.",
                "  Une réponse de forum n'est pas une preuve : certaines sont fausses, à vérifier sur la fiche technique.", '']
    for r in q.head(A.max).iter_rows(named=True):
        rapport += [f"== {texte_brut(r['Title'], 160)} ({(r['CreationDate'] or '')[:10]}) — https://electronics.stackexchange.com/q/{r['Id']}",
                    '   étiquettes : ' + ', '.join(x for x in (r['Tags'] or '').split('|') if x),
                    '   question : ' + texte_brut(r['Body'], 260),
                    '   réponse gardée par le jeu : ' + texte_brut(r['Answer'], 320), '']

nom = 'fonction.txt' if A.motif != '-' else 'pieges.txt'
open(os.path.join(A.sortie, nom), 'w', encoding='utf-8').write('\n'.join(rapport) + '\n')
print('\n'.join(rapport))
