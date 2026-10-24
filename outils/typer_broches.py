"""Donne un vrai type à chaque broche des symboles téléchargés par easyeda2kicad (entrée, sortie, alimentation, passive…).
Sans ces types, le contrôle électrique de KiCad est presque aveugle : constaté le 24/10/2026 sur la radio v4, presque toutes
les broches étaient « Unspecified », et KiCad ne pouvait voir ni deux sorties reliées, ni une alimentation non fournie.
D'où viennent les types, dans l'ordre :
  1. la bibliothèque officielle de KiCad (règles KLC), pour les pièces listées dans bibliotheque/empreintes/symboles-officiels.json,
     broche par broche, par numéro ou par nom ;
  2. une broche qui porte le même nom qu'une autre broche du même symbole (languette, broches doublées) : « passive »,
     comme dans la bibliothèque officielle ;
  3. une broche nommée NC : « no_connect » ;
  4. une pièce passive (résistance, condensateur, bobine, diode ou LED, quartz, bouton, prise, pastille de test),
     reconnue à ses repères dans correspondance.json : toutes ses broches « passive » ;
  5. sinon, le type d'origine est gardé, et la broche est signalée « non typée ».
Le résultat va dans bibliotheque/empreintes/types-broches.json, un fichier qu'on peut relire ; schema.py l'applique.
Les numéros de broches restent ceux de LCSC : seuls les types changent, donc rien ne peut se décaler.
La comparaison des noms (LCSC ↔ KiCad) est écrite dans le rapport : c'est là qu'on verrait une numérotation différente.
Il faut une copie de la bibliothèque officielle (les seuls symboles utiles suffisent) :
  git clone --depth 1 --filter=blob:none --sparse https://gitlab.com/kicad/libraries/kicad-symbols.git DOSSIER
  cd DOSSIER && git sparse-checkout set --no-cone /RF_Module.kicad_symdir/ESP32-S3-WROOM-1.kicad_sym …
  (le script dit lui-même quels fichiers il lui faut).
Usage : python3 outils/typer_broches.py bibliotheque/ DOSSIER_KICAD_SYMBOLS"""
import json, os, re, subprocess, sys, time
ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
from sexpr import lire_sexpr, broches, numero_nom, propriete, sans_guillemets

BIB, KS = sys.argv[1], sys.argv[2]
EMP = os.path.join(BIB, 'empreintes')
fichier_sym = next(os.path.join(EMP, f) for f in os.listdir(EMP) if f.endswith('.kicad_sym'))
officiels = json.load(open(os.path.join(EMP, 'symboles-officiels.json'), encoding='utf-8'))
corr = json.load(open(os.path.join(EMP, 'correspondance.json'), encoding='utf-8'))
PASSIVES = re.compile(r'^(R|C|L|D|LED|Y|X|SW|TP|J|FB|F|BZ|H)\d')
lib = lire_sexpr(open(fichier_sym, encoding='utf-8').read())


def symbole_officiel(chemin):
    """Broches d'un symbole officiel (numéro → (nom, type)), parent compris quand il « étend » un autre symbole."""
    dossier, nom = chemin.split('/')
    f = os.path.join(KS, dossier + '.kicad_symdir', nom + '.kicad_sym')
    if not os.path.exists(f):
        sys.exit(f"Il manque {f} : git sparse-checkout add '/{dossier}.kicad_symdir/{nom}.kicad_sym' dans {KS}")
    s = next(x for x in lire_sexpr(open(f, encoding='utf-8').read()) if isinstance(x, list) and x[0] == 'symbol')
    parent = next((sans_guillemets(x[1]) for x in s if isinstance(x, list) and x[0] == 'extends'), None)
    out = symbole_officiel(f'{dossier}/{parent}') if parent else {}
    for p in broches(s):
        num, nom_b = numero_nom(p)
        out[num] = (nom_b, p[1])
    return out


def jetons(nom, synonymes=None):
    """Nom de broche → ensemble de jetons comparables : « ~{RST} » = « RST# » = « RST » ; « GPO2/[~{INT}] » = {GPO2, INT}."""
    n = re.sub(r'[~{}\[\]#]', '', nom.upper())
    js = set()
    for j in re.split(r'[/,]', n):
        j = j.strip()
        if not j:
            continue
        j = (synonymes or {}).get(j, j)
        js.add(j)
        if len(j) > 2 and j.endswith('B') and not j.startswith('V'):       # SENB, INTB : actif bas, comme ~{SEN}
            js.add(j[:-1])
    return js


resultat, rapport, a_verifier = {}, [], []
for s in lib:
    if not (isinstance(s, list) and s and s[0] == 'symbol'):
        continue
    lcsc = propriete(s, 'LCSC Part')
    if not lcsc:
        continue
    pins = broches(s)
    noms = [numero_nom(p) for p in pins]
    types, d_apres = {}, {}
    ids = corr.get(lcsc, {}).get('ids', [])
    o = officiels['pieces'].get(lcsc)
    if o:
        off = symbole_officiel(o['symbole'])
        syn = {k.upper(): v.upper() for k, v in o.get('synonymes', {}).items()}
        for num, nom in noms:
            if o['par'] == 'numero' and num in off:
                types[num], d_apres[num] = off[num][1], f"officiel n° {num}"
                if jetons(nom, syn).isdisjoint(jetons(off[num][0])):
                    a_verifier.append(f"{lcsc} broche {num} : « {nom} » chez LCSC, « {off[num][0]} » chez KiCad")
            elif o['par'] == 'nom':
                trouve = [(n2, t) for n2, (nm2, t) in off.items() if not jetons(nom, syn).isdisjoint(jetons(nm2))]
                exacts = [(n2, t) for n2, t in trouve if jetons(off[n2][0]) == jetons(nom, syn)]
                if len({t for _, t in exacts}) == 1:              # « LOUT/DFS » = « LOUT/[DFS] », pas « DFS » tout seul
                    trouve = exacts
                ty = {t for _, t in trouve}
                if len(ty) == 1:
                    types[num], d_apres[num] = ty.pop(), f"officiel « {trouve[0][0]} »"
                elif len(ty) > 1:
                    a_verifier.append(f"{lcsc} broche {num} « {nom} » : plusieurs types possibles chez KiCad ({', '.join(sorted(ty))}), non typée")
    for num, nom in noms:
        if num in types:
            continue
        doublons = [n2 for n2, nm2 in noms if nm2 == nom and n2 != num and n2 in types]
        if doublons:
            types[num], d_apres[num] = 'passive', f"même nom que la broche {doublons[0]}"
        elif nom.upper() == 'NC':
            types[num], d_apres[num] = 'no_connect', 'nommée NC'
    if ids and all(PASSIVES.match(i) for i in ids):
        for num, nom in noms:
            if num not in types:
                types[num], d_apres[num] = 'passive', f"pièce passive ({', '.join(ids[:4])})"
    non_types = [f"{num} ({nom})" for num, nom in noms if num not in types]
    resultat[lcsc] = {'symbole': sans_guillemets(s[1]), 'reperes': ids, 'officiel': o['symbole'] if o else None,
                      'broches': {num: {'type': types[num], 'd_apres': d_apres[num]} for num, _ in noms if num in types}}
    rapport.append(f"{lcsc} {sans_guillemets(s[1])} ({', '.join(ids[:5]) or '?'}) : {len(types)}/{len(noms)} broches typées"
                   + (f" ; non typées : {', '.join(non_types)}" if non_types else ''))

try:
    commit = subprocess.run(['git', '-C', KS, 'log', '-1', '--format=%h %cs'], capture_output=True, text=True).stdout.strip()
except OSError:
    commit = '?'
sortie = {'note': "Types des broches, appliqués par schema.py aux symboles d'easyeda2kicad. Fait par outils/typer_broches.py : "
                  "ne pas corriger à la main, corriger symboles-officiels.json et relancer.",
          'fait_le': time.strftime('%d/%m/%Y'), 'bibliotheque_officielle': f"kicad-symbols {commit}",
          'pieces': resultat}
json.dump(sortie, open(os.path.join(EMP, 'types-broches.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('\n'.join(rapport))
if a_verifier:
    print("\nNoms différents entre LCSC et KiCad (à regarder une fois : une numérotation décalée se verrait ici) :")
    print('\n'.join('  ' + a for a in a_verifier))
print(f"\nÉcrit : {os.path.join(EMP, 'types-broches.json')}")
