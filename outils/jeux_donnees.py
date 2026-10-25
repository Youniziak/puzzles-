"""Les jeux de données publics où la chaîne va chercher comment d'autres ont fait (montages réels, recherche par
fonction, pièges connus). Rien de tout cela n'est dans le dépôt : on télécharge chez soi, dans un cache, on lit et on
cite. Chaque projet cité garde sa propre licence, quoi qu'en dise l'étiquette du jeu : c'est la licence du projet
d'origine qui compte (même règle que pour la bibliothèque de LCSC/EasyEDA, voir LICENCE.md).

Cache : variable d'environnement CHAINE_CACHE, sinon ~/.cache/chaine-puzzle (environ 420 Mo si tout est téléchargé :
280 Mo pour l'index des valeurs, 130 Mo pour Electronics Stack Exchange, le reste en petits fichiers).

Règle : toutes les liaisons que la chaîne montre sortent de KiCad lui-même, lisant le schéma d'origine. Aucune ne vient
d'une conversion faite par un jeu. Raison, vérifiée le 25/10/2026 sur le jeu « circuits » (AbijahKaj,
« kicad-netlist-sft », 100 000 circuits déjà réduits à leurs liaisons, presque tous tirés d'Open Schematics : 21 841
de ses 22 675 dépôts GitHub y sont) : ses liaisons sont recalculées par un convertisseur, et fausses dans des cas
vérifiés. Sur Ahmed-H300/Carcotech, la masse de l'ampli PAM8403 est fondue dans le +3V3 et ses deux entrées n'ont plus
de liaison, alors que KiCad, lisant le schéma d'origine, les trouve reliées au lecteur DFR0299. Sur 4 000 circuits
tirés au hasard, 192 (4,8 %) ont une puce dont la masse et l'alimentation tombent sur le même réseau. Ce jeu ne sert
donc que d'index : il dit quels dépôts ont une pièce de telle valeur, et le schéma lui-même est pris dans Open
Schematics.

Jeu regardé et écarté : mascarade (questions et réponses d'électronique), surtout écrit par une IA, pas par des gens
qui ont monté la carte."""
import os, re, sys, time, urllib.request

HF = 'https://huggingface.co/datasets/'

JEUX = {
    'ohmatic': {
        'nom': 'Ohmatic, « human-verified schematics » (1 000 schémas KiCad et Eagle, avec un niveau de confiance)',
        'page': HF + 'Ohmatic/human-verified-schematics-v1',
        'index': HF + 'Ohmatic/human-verified-schematics-v1/resolve/main/dataset.json',
        'fichiers': HF + 'Ohmatic/human-verified-schematics-v1/resolve/main/',
        'licence': "CC BY 4.0 pour l'index d'Ohmatic ; chaque schéma garde la licence de son dépôt d'origine",
    },
    'kicad9plus': {
        'nom': 'electron-rare, « kicad9plus » (environ 300 schémas KiCad 9 et plus, rangés par licence)',
        'page': HF + 'electron-rare/kicad9plus-permissive',
        'index': [HF + 'electron-rare/kicad9plus-permissive/resolve/main/dataset.jsonl',
                  HF + 'electron-rare/kicad9plus-copyleft/resolve/main/dataset.jsonl'],
        'licence': 'licence de chaque schéma donnée par le jeu (Apache, MIT, GPL, CERN-OHL-S…)',
    },
    'open-schematics': {
        'nom': ('bshada, « Open Schematics » (88 000 schémas tirés de 30 000 dépôts GitHub, avec la description de '
                'chaque dépôt ; une feuille par schéma)'),
        'page': HF + 'bshada/open-schematics',
        'index': 'hf://datasets/bshada/open-schematics/data/*.parquet',
        'licence': "CC BY 4.0 pour le jeu ; chaque schéma garde la licence de son dépôt d'origine",
    },
    'circuits': {
        'nom': ('AbijahKaj, « kicad-netlist-sft » (sert seulement d\'index : quels dépôts ont une pièce de telle valeur ; '
                'ses liaisons ne sont pas utilisées)'),
        'page': HF + 'AbijahKaj/kicad-netlist-sft-dataset',
        'index': HF + 'AbijahKaj/kicad-netlist-sft-dataset/resolve/main/data/train-00000-of-00001.parquet',
        'licence': "Apache 2.0 pour le jeu ; chaque circuit garde la licence de son dépôt d'origine",
    },
    'electronics-se': {
        'nom': 'Electronics Stack Exchange (95 000 questions avec une réponse, de 2009 à mars 2024)',
        'page': HF + 'bshada/electronics.stackexchange.com',
        'index': HF + 'bshada/electronics.stackexchange.com/resolve/refs%2Fconvert%2Fparquet/default/train/0000.parquet',
        'licence': ('CC BY-SA (3.0 avant mai 2018, 4.0 après) ; les auteurs sont nommés sur la page de chaque question, '
                    'à citer avec son lien'),
    },
}


def cache():
    d = os.environ.get('CHAINE_CACHE') or os.path.join(os.path.expanduser('~'), '.cache', 'chaine-puzzle')
    os.makedirs(d, exist_ok=True)
    return d


def telecharger(url, nom):
    """Chemin local du fichier, téléchargé la première fois seulement (le proxy du système est utilisé)."""
    chemin = os.path.join(cache(), nom)
    if os.path.exists(chemin):
        return chemin
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    print(f'  téléchargement de {nom}…', file=sys.stderr, flush=True)
    t = time.time()
    tmp = chemin + '.part'
    with urllib.request.urlopen(url, timeout=120) as r, open(tmp, 'wb') as f:
        while True:
            bloc = r.read(1 << 20)
            if not bloc:
                break
            f.write(bloc)
    os.replace(tmp, chemin)
    print(f'  … {os.path.getsize(chemin) / 1e6:.0f} Mo en {time.time() - t:.0f} s', file=sys.stderr, flush=True)
    return chemin


def index_open_schematics():
    """Chemin de l'index local d'Open Schematics : pour chaque schéma, le dépôt, sa description, ses composants (noms
    des symboles), ses extensions et le fichier du jeu où il se trouve. Le jeu pèse 317 Go (surtout des images) : on
    n'en lit que ces colonnes, une seule fois (environ 3 minutes, 3 Mo), puis chaque recherche ne relit que les
    fichiers utiles."""
    chemin = os.path.join(cache(), 'open-schematics', 'index.parquet')
    if os.path.exists(chemin):
        return chemin
    import polars as pl
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    print("  index d'Open Schematics : lecture de 939 fichiers à distance (quelques minutes, une seule fois)…",
          file=sys.stderr, flush=True)
    t = time.time()
    (pl.scan_parquet(JEUX['open-schematics']['index'], include_file_paths='fichier')
       .select(['name', 'description', 'components_used', 'extensions_used', 'fichier'])
       .with_columns(pl.col('fichier').str.extract(r'(data/[^/?]+\.parquet)'))
       .collect().write_parquet(chemin + '.part'))
    os.replace(chemin + '.part', chemin)
    print(f'  … {os.path.getsize(chemin) / 1e6:.0f} Mo en {time.time() - t:.0f} s', file=sys.stderr, flush=True)
    return chemin


def fichier_open_schematics(nom_fichier):
    """Adresse lisible par polars d'un fichier du jeu, d'après la colonne « fichier » de l'index."""
    return 'hf://datasets/bshada/open-schematics/' + nom_fichier


def depot_de(url):
    """« propriétaire/dépôt » en minuscules, à partir d'une adresse GitHub ou d'un nom déjà sous cette forme."""
    m = re.search(r'github\.com/([^/\s]+)/([^/\s#?]+)', url or '')
    if m:
        return f'{m.group(1)}/{m.group(2)}'.removesuffix('.git').lower()
    return (url or '').strip().lower()
