"""Télécharge chez soi la bibliothèque des composants de la chaîne : empreintes, symboles et modèles 3D de LCSC/EasyEDA,
avec easyeda2kicad (logiciel libre, AGPL-3.0).

Pourquoi ces fichiers ne sont pas dans le dépôt : les conditions d'utilisation d'EasyEDA interdisent de republier leur
contenu (lues le 25/10/2026 : https://easyeda.com/page/legal). Chacun les télécharge donc pour son propre usage.

Ce que fait le script :
  1. lit la liste des pièces (numéros LCSC) dans bibliotheque/empreintes/correspondance.json ;
  2. les télécharge avec easyeda2kicad dans un dossier temporaire ;
  3. applique les retouches décidées pour la chaîne, décrites et expliquées dans bibliotheque/empreintes/retouches.json ;
  4. compare chaque fichier à ce qui est attendu (bibliotheque/empreintes/attendu.json : des sommes SHA-256, pas les
     fichiers eux-mêmes). Si LCSC a changé une pièce depuis, le script le dit, fichier par fichier : à relire avant
     de faire une carte ;
  5. range le tout dans bibliotheque/empreintes/ (NOM.pretty, NOM.kicad_sym, NOM.3dshapes).

Usage : python3 outils/telecharger_bibliotheque.py [--bibliotheque bibliotheque] [--easyeda2kicad CHEMIN] [--remplacer]
        python3 outils/telecharger_bibliotheque.py --noter-attendu   (après une mise à jour voulue : écrit les nouvelles sommes)
Sortie : 0 si tout est conforme, 3 si des fichiers diffèrent de l'attendu (la bibliothèque est quand même rangée),
         1 en cas d'erreur."""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile

ICI = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- outils de texte
def fin_sexpr(texte, debut):
    """Indice juste après la parenthèse qui ferme l'expression ouverte en `debut` (les chaînes entre guillemets comptent pour rien)."""
    niveau, i, dans_chaine = 0, debut, False
    while i < len(texte):
        c = texte[i]
        if dans_chaine:
            if c == '\\':
                i += 1
            elif c == '"':
                dans_chaine = False
        elif c == '"':
            dans_chaine = True
        elif c == '(':
            niveau += 1
        elif c == ')':
            niveau -= 1
            if niveau == 0:
                return i + 1
        i += 1
    raise ValueError('parenthèses déséquilibrées')


def bloc_symbole(texte, nom):
    """(début, fin) du symbole `nom` dans un fichier .kicad_sym."""
    m = re.search(r'\(symbol "' + re.escape(nom) + r'"', texte)
    if not m:
        raise KeyError(f'symbole {nom} introuvable')
    return m.start(), fin_sexpr(texte, m.start())


def meme_format(origine, valeur):
    """Écrit `valeur` avec autant de décimales que le nombre d'origine (« -2.38 » → « -2.39 », « 1.100 » → « 1.080 »)."""
    dec = len(origine.split('.')[1]) if '.' in origine else 0
    return f'{valeur:.{dec}f}'


# ---------------------------------------------------------------- les retouches
PAD = re.compile(r'\(pad (?P<nom>"[^"]*"|\S+) (?P<type>\S+) (?P<forme>\S+) \(at (?P<x>\S+) (?P<y>[^\s)]+)(?: (?P<rot>[^\s)]+))?\) \(size (?P<w>\S+) (?P<h>[^\s)]+)\)')


def raccourcir_pastilles(dossier_pretty, r):
    f = os.path.join(dossier_pretty, r['empreinte'] + '.kicad_mod')
    texte = open(f, encoding='utf-8').read()
    pads = list(PAD.finditer(texte))
    trous = [(float(p['x']), float(p['y'])) for p in pads if p['nom'] == '""' or p['type'] == 'np_thru_hole']
    if not trous:
        raise ValueError(f"{r['empreinte']} : pas de trou de fixation trouvé")
    for nom in r['pastilles']:
        p = next((p for p in pads if p['nom'] == nom), None)
        if p is None:
            raise KeyError(f"{r['empreinte']} : pastille {nom} introuvable")
        if float(p['rot'] or 0) % 180:
            raise ValueError(f"{r['empreinte']} : pastille {nom} tournée de {p['rot']}°, cas non prévu")
        x, y, w, h = float(p['x']), float(p['y']), float(p['w']), float(p['h'])
        tx, ty = min(trous, key=lambda t: (t[0] - x) ** 2 + (t[1] - y) ** 2)
        d = r['mm']
        nx, ny, nw, nh = p['x'], p['y'], p['w'], p['h']
        if h >= w:  # pastille en long dans le sens y : on la raccourcit du côté du trou, l'autre bout ne bouge pas
            ny, nh = meme_format(p['y'], y - (1 if ty > y else -1) * d / 2), meme_format(p['h'], h - d)
        else:
            nx, nw = meme_format(p['x'], x - (1 if tx > x else -1) * d / 2), meme_format(p['w'], w - d)
        rot = f" {p['rot']}" if p['rot'] else ''
        nouveau = f"(pad {p['nom']} {p['type']} {p['forme']} (at {nx} {ny}{rot}) (size {nw} {nh})"
        texte = texte.replace(p.group(0), nouveau, 1)
    open(f, 'w', encoding='utf-8').write(texte)
    return f"{r['empreinte']} : pastilles {', '.join(r['pastilles'])} raccourcies de {r['mm']} mm côté trou"


def broches_passives(fichier_sym, r):
    texte = open(fichier_sym, encoding='utf-8').read()
    n = 0
    for nom in r['symboles']:
        a, b = bloc_symbole(texte, nom)
        morceau, k = re.subn(r'\(pin (?!passive )\w+ line', '(pin passive line', texte[a:b])
        texte = texte[:a] + morceau + texte[b:]
        n += k
    open(fichier_sym, 'w', encoding='utf-8').write(texte)
    return f"{n} broches passées en « passive » dans {len(r['symboles'])} symboles"


def renommer_broche(fichier_sym, r):
    texte = open(fichier_sym, encoding='utf-8').read()
    a, b = bloc_symbole(texte, r['symbole'])
    i = a
    while True:
        i = texte.find('(pin ', i, b)
        if i < 0:
            raise KeyError(f"{r['symbole']} : broche {r['broche']} introuvable")
        j = fin_sexpr(texte, i)
        broche = texte[i:j]
        if f'(number "{r["broche"]}"' in broche:
            avant = f'(name "{r["avant"]}"'
            if avant not in broche:
                raise ValueError(f"{r['symbole']} : la broche {r['broche']} ne s'appelle plus « {r['avant']} »")
            texte = texte[:i] + broche.replace(avant, f'(name "{r["nom"]}"', 1) + texte[j:]
            break
        i = j
    open(fichier_sym, 'w', encoding='utf-8').write(texte)
    return f"{r['symbole']} : broche {r['broche']} renommée « {r['nom']} » (avant : « {r['avant']} »)"


# ---------------------------------------------------------------- comparaison à l'attendu
def sommes(dossier, nom):
    res = {}
    for sous in (nom + '.pretty', nom + '.3dshapes'):
        for f in sorted(os.listdir(os.path.join(dossier, sous))):
            res[f'{sous}/{f}'] = hashlib.sha256(open(os.path.join(dossier, sous, f), 'rb').read()).hexdigest()
    res[nom + '.kicad_sym'] = hashlib.sha256(open(os.path.join(dossier, nom + '.kicad_sym'), 'rb').read()).hexdigest()
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--bibliotheque', default=os.path.join(ICI, '..', 'bibliotheque'))
    ap.add_argument('--easyeda2kicad', default=None, help='chemin du programme easyeda2kicad (sinon : celui du PATH)')
    ap.add_argument('--remplacer', action='store_true', help='remplacer une bibliothèque déjà téléchargée')
    ap.add_argument('--noter-attendu', action='store_true', help="écrire les sommes du résultat dans attendu.json")
    a = ap.parse_args()

    emp = os.path.join(os.path.abspath(a.bibliotheque), 'empreintes')
    corr = json.load(open(os.path.join(emp, 'correspondance.json'), encoding='utf-8'))
    ret = json.load(open(os.path.join(emp, 'retouches.json'), encoding='utf-8'))
    nom = ret['nom_bibliotheque']
    dest = [os.path.join(emp, nom + s) for s in ('.pretty', '.kicad_sym', '.3dshapes')]
    if any(os.path.exists(d) for d in dest) and not (a.remplacer or a.noter_attendu):
        sys.exit(f"La bibliothèque est déjà là ({emp}). Pour la retélécharger : --remplacer")

    prog = a.easyeda2kicad or shutil.which('easyeda2kicad') or os.path.join(os.path.dirname(sys.executable), 'easyeda2kicad')
    if not os.path.exists(prog) and not shutil.which(prog):
        sys.exit("easyeda2kicad introuvable : l'installer (pip install easyeda2kicad==1.0.1) ou donner --easyeda2kicad CHEMIN")

    tmp = tempfile.mkdtemp(prefix='bibliotheque-lcsc-')
    try:
        os.makedirs(os.path.join(tmp, 'lib'))
        ids = list(corr)
        print(f'Téléchargement de {len(ids)} pièces depuis LCSC/EasyEDA…', flush=True)
        r = subprocess.run([prog, '--full', '--lcsc_id', *ids, '--output', 'lib/' + nom],
                           cwd=tmp, capture_output=True, text=True)
        journal = r.stdout + r.stderr
        erreurs = [l for l in journal.splitlines() if '[ERROR]' in l and 'already exists' not in l]
        if erreurs:  # « already exists » : plusieurs pièces partagent la même empreinte, c'est normal
            print('\n'.join(erreurs))
            sys.exit('Le téléchargement a échoué pour au moins une pièce (connexion ? numéro LCSC ?).')
        lib = os.path.join(tmp, 'lib')
        manque = [c for c, v in corr.items() if not os.path.exists(os.path.join(lib, nom + '.pretty', v['empreinte'] + '.kicad_mod'))]
        if manque:
            sys.exit(f"Empreintes absentes après téléchargement : {', '.join(manque)}")

        print('Retouches de la chaîne (retouches.json) :')
        for rt in ret['retouches']:
            if rt['type'] == 'raccourcir_pastilles':
                msg = raccourcir_pastilles(os.path.join(lib, nom + '.pretty'), rt)
            elif rt['type'] == 'broches_passives':
                msg = broches_passives(os.path.join(lib, nom + '.kicad_sym'), rt)
            elif rt['type'] == 'renommer_broche':
                msg = renommer_broche(os.path.join(lib, nom + '.kicad_sym'), rt)
            else:
                sys.exit(f"retouche inconnue : {rt['type']}")
            print('  -', msg)

        obtenu = sommes(lib, nom)
        f_att = os.path.join(emp, 'attendu.json')
        code = 0
        if a.noter_attendu:
            json.dump({'a_quoi_ca_sert': "Sommes SHA-256 de la bibliothèque téléchargée et retouchée, pour voir si LCSC change une pièce. "
                                         "Ce ne sont pas les fichiers eux-mêmes.", 'fichiers': obtenu},
                      open(f_att, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            print(f'Sommes notées dans {f_att} ({len(obtenu)} fichiers).')
        elif os.path.exists(f_att):
            attendu = json.load(open(f_att, encoding='utf-8'))['fichiers']
            diff = sorted(k for k in attendu.keys() & obtenu.keys() if attendu[k] != obtenu[k])
            absents, nouveaux = sorted(attendu.keys() - obtenu.keys()), sorted(obtenu.keys() - attendu.keys())
            if diff or absents or nouveaux:
                code = 3
                print("Attention : la bibliothèque n'est plus celle qui a servi aux cartes. LCSC a peut-être changé ces pièces :")
                for k in diff:
                    print('  - différent :', k)
                for k in absents:
                    print('  - absent    :', k)
                for k in nouveaux:
                    print('  - nouveau   :', k)
                print('À relire avant de faire une carte (contrôle de la chaîne, puis --noter-attendu si tout va bien).')
            else:
                print(f'Conforme : les {len(obtenu)} fichiers sont identiques à ceux qui ont servi aux cartes.')

        for d, s in zip(dest, ('.pretty', '.kicad_sym', '.3dshapes')):
            if os.path.isdir(d):
                shutil.rmtree(d)
            elif os.path.exists(d):
                os.remove(d)
            shutil.move(os.path.join(lib, nom + s), d)
        print(f'Bibliothèque rangée dans {emp}')
        return code
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
