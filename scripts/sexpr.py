"""Lecture et écriture des fichiers de KiCad (expressions S), partagées par schema.py et outils/typer_broches.py.
Les chaînes gardent leurs guillemets : ce qu'on lit se réécrit tel quel."""
import re


def lire_sexpr(texte):
    jetons = re.findall(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+', texte)
    pile, cur = [], []
    for j in jetons:
        if j == '(':
            pile.append(cur); cur = []
        elif j == ')':
            fini = cur; cur = pile.pop(); cur.append(fini)
        else:
            cur.append(j)
    return cur[0]


def ecrire_sexpr(e, ind=0):
    if not isinstance(e, list):
        return e
    if all(not isinstance(x, list) for x in e):
        return '(' + ' '.join(e) + ')'
    tete = [x for x in e if not isinstance(x, list)]
    corps = [x for x in e if isinstance(x, list)]
    pad = '  ' * (ind + 1)
    return '(' + ' '.join(tete) + '\n' + '\n'.join(pad + ecrire_sexpr(x, ind + 1) for x in corps) + ')'


def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


def sans_guillemets(s):
    return s[1:-1].replace('\\"', '"').replace('\\\\', '\\') if isinstance(s, str) and len(s) >= 2 and s[0] == s[-1] == '"' else s


def propriete(sym, nom):
    """Valeur d'une propriété d'un symbole (sans guillemets), ou None."""
    return next((sans_guillemets(p[2]) for p in sym if isinstance(p, list) and len(p) > 2 and p[0] == 'property'
                 and sans_guillemets(p[1]) == nom), None)


def broches(sym):
    """Toutes les broches d'un symbole (unités comprises) : listes [« pin », type, style, …], modifiables sur place."""
    out = []
    def parcours(e):
        for x in e:
            if isinstance(x, list):
                if x and x[0] == 'pin' and len(x) > 2 and not isinstance(x[1], list):
                    out.append(x)
                else:
                    parcours(x)
    parcours(sym)
    return out


def numero_nom(pin):
    num = next((sans_guillemets(a[1]) for a in pin if isinstance(a, list) and a[0] == 'number'), '')
    nom = next((sans_guillemets(a[1]) for a in pin if isinstance(a, list) and a[0] == 'name'), '')
    return num, nom
