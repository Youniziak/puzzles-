"""Chaîne puzzle — les composants sont-ils disponibles chez JLCPCB, pour faire assembler la carte ?
À lancer juste avant de commander : les stocks changent tous les jours. Il faut une connexion internet.
Pour chaque pièce posée (les sorties en cuivre nu ne comptent pas) :
  - le stock chez JLCPCB, et s'il couvre le nombre de cartes voulu ;
  - le type de pièce : « de base » (déjà sur les machines) ou « étendue » (frais de chargement en plus, par type de pièce) ;
  - le prix unitaire pour la quantité demandée.
Source : la recherche de pièces du site de JLCPCB (interface non documentée, elle peut changer) ;
en secours, la fiche produit de LCSC, le fournisseur de JLCPCB (le stock LCSC n'est pas toujours celui de JLCPCB).
Usage : python3 disponibilite.py cartes/ma-carte.json [nombre de cartes, 5 par défaut] [fichier de sortie]"""
import json, re, sys, time, urllib.request
from collections import defaultdict
from description import Carte

CARTE = Carte(sys.argv[1])
N = int(sys.argv[2]) if len(sys.argv) > 2 else 5
SORTIE = sys.argv[3] if len(sys.argv) > 3 else None

pieces = defaultdict(lambda: {'reperes': [], 'mpn': ''})
for b in CARTE.blocs:
    non_poses = set(b.bloc.get('non_poses', []))
    for p in b.design['parts']:
        if p['id'] in non_poses or not p.get('lcscPartNumber'):
            continue
        e = pieces[p['lcscPartNumber']]
        e['reperes'].append(CARTE.repere(b, p['id'])); e['mpn'] = p.get('mpn', '')

def jlcpcb(code):
    req = urllib.request.Request('https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList',
                                 data=json.dumps({'keyword': code, 'currentPage': 1, 'pageSize': 10}).encode(),
                                 headers={'Content-Type': 'application/json', 'User-Agent': 'chaine-puzzle'})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    for c in ((d.get('data') or {}).get('componentPageInfo') or {}).get('list') or []:
        if c.get('componentCode') == code:
            return c
    return None

def lcsc(code):
    req = urllib.request.Request(f'https://wmsc.lcsc.com/ftps/wm/product/detail?productCode={code}', headers={'User-Agent': 'chaine-puzzle'})
    return (json.load(urllib.request.urlopen(req, timeout=30)).get('result') or {})

def prix(paliers, q, cle_debut='startNumber', cle_prix='productPrice'):
    ok = [p for p in paliers or [] if p.get(cle_debut, 1) <= q]
    return max(ok, key=lambda p: p.get(cle_debut, 1)).get(cle_prix) if ok else None

lignes, manques, etendues, total = [], [], [], 0.0
for code, e in sorted(pieces.items(), key=lambda kv: kv[1]['reperes'][0]):
    besoin = len(e['reperes']) * N
    source, stock, genre, pu = 'JLCPCB', None, '?', None
    try:
        c = jlcpcb(code)
        if c:
            stock = c.get('stockCount')
            genre = 'de base' if c.get('componentLibraryType') == 'base' else ('étendue préférée' if c.get('preferredComponentFlag') else 'étendue')
            pu = prix(c.get('componentPrices'), besoin)
    except Exception as ex:
        c = None
    if stock is None:
        try:
            r = lcsc(code); source = 'LCSC (secours)'
            stock = r.get('stockNumber'); pu = prix(r.get('productPriceList'), besoin, 'ladder', 'usdPrice')
        except Exception as ex:
            source = f'injoignable ({type(ex).__name__})'
    ok = stock is not None and stock >= besoin
    if not ok:
        manques.append(f"{e['mpn']} ({code}, {', '.join(e['reperes'])}) : stock {stock if stock is not None else 'inconnu'}, il en faut {besoin}")
    if genre.startswith('étendue'):
        etendues.append(f"{e['mpn']} ({genre})")
    if pu:
        total += pu * besoin
    lignes.append(f"{'✓' if ok else '✗'} {code:10s} {e['mpn'][:28]:28s} {', '.join(e['reperes'])[:24]:24s} besoin {besoin:4d}  "
                  f"stock {stock if stock is not None else '?':>7}  {genre:17s} {('%.4f $' % pu) if pu else '?':>10}  [{source}]")
    time.sleep(0.5)                      # ne pas bombarder le site

texte = [f"Disponibilité des composants chez JLCPCB — {CARTE.nom}, pour {N} carte(s) — {time.strftime('%d/%m/%Y %H:%M')}", ''] + lignes + ['']
texte.append(f"{len(pieces)} pièces différentes ; coût des composants pour {N} carte(s) : environ {total:.2f} $ (hors carte, pose et port)")
texte.append(f"Pièces étendues : {len(etendues)} type(s), chacun avec des frais de chargement chez JLCPCB (voir leur tarif) : " + ('; '.join(etendues) or 'aucune'))
if manques:
    texte.append(f"✗ {len(manques)} pièce(s) manquante(s) ou en quantité insuffisante : JLCPCB ne pourra pas tout assembler.")
    texte += ['  - ' + m for m in manques]
else:
    texte.append('✓ Toutes les pièces sont en stock en quantité suffisante, aujourd\'hui.')
print('\n'.join(texte))
if SORTIE:
    open(SORTIE, 'w', encoding='utf-8').write('\n'.join(texte) + '\n')
sys.exit(1 if manques else 0)
