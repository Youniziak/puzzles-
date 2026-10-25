"""Essai d'EDeA (Fully Automated OÜ, licence européenne EUPL-1.2, gitlab.com/edea-dev/edea) : sait-il lire les
fichiers KiCad de la chaîne ? C'est la condition pour s'en servir plus tard : fusionner un bloc (schéma et carte)
dans une carte, ou partager nos blocs sur son portail.
Tourne sur les machines de GitHub (workflow .github/workflows/edea.yml) : dans l'espace de travail de Claude, le
garde-fou refuse d'installer EDeA (« code venu de l'extérieur », constaté le 24/10/2026).
Pour chaque schéma et chaque carte de resultats/ (sans les copies du dossier de relecture et des fabricants) :
lecture, puis aller-retour : EDeA réécrit le fichier, et on compte chaque sorte d'élément (symboles, fils, pistes,
vias...) avant et après, pour voir ce qu'il perd. Les fichiers réécrits sont gardés, pour les rouvrir dans KiCad 10.
Usage : python3 essai_edea.py dossier_resultats dossier_sortie"""
import json
import re
import sys
import time
import traceback
from collections import Counter
from importlib.metadata import version as version_paquet
from pathlib import Path

from edea.kicad.parser import parse_pcb, parse_schematic
from edea.kicad.serializer import to_str

CHAINE = re.compile(r'"(?:[^"\\]|\\.)*"')
ETIQUETTE = re.compile(r'\(([a-z_][a-z0-9_]*)')
COPIES = ('dossier-relecture', 'fabricants')


def compter(texte):
    """Combien de fois chaque sorte d'élément apparaît (les textes entre guillemets sont mis de côté)."""
    return Counter(ETIQUETTE.findall(CHAINE.sub('""', texte)))


def en_tete(texte):
    """Le numéro de format du fichier, et la version du logiciel qui l'a écrit."""
    numero = re.search(r'\(version (\d+)\)', texte)
    outil = re.search(r'\(generator_version "([^"]*)"\)', texte)
    return (numero.group(1) if numero else '?'), (outil.group(1) if outil else '?')


def panne(e):
    """L'erreur en une ligne, et l'endroit d'EDeA où elle s'est produite."""
    pile = traceback.extract_tb(e.__traceback__)
    ou = f'{Path(pile[-1].filename).name}:{pile[-1].lineno} ({pile[-1].name})' if pile else '?'
    message = ' '.join(str(e).split())
    return f'{type(e).__name__} : {message[:400]}', ou


def essayer(chemin, racine, sortie):
    texte = chemin.read_text(encoding='utf-8')
    numero, outil = en_tete(texte)
    lire = parse_schematic if chemin.suffix == '.kicad_sch' else parse_pcb
    nom = str(chemin.relative_to(racine))
    res = {'fichier': nom, 'format': numero, 'fait_par': outil}
    debut = time.time()
    try:
        objet = lire(texte)
    except Exception as e:
        res['lu'] = False
        res['erreur'], res['ou'] = panne(e)
        return res
    res['lu'] = True
    res['secondes'] = round(time.time() - debut, 1)
    try:
        texte2 = to_str(objet)
    except Exception as e:
        res['reecrit'] = False
        res['erreur'], res['ou'] = panne(e)
        return res
    res['reecrit'] = True
    cible = sortie / 'reecrits' / nom
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(texte2, encoding='utf-8')
    avant, apres = compter(texte), compter(texte2)
    ecarts = sorted(((k, avant[k], apres[k]) for k in set(avant) | set(apres) if avant[k] != apres[k]),
                    key=lambda x: (-abs(x[1] - x[2]), x[0]))
    res['elements_avant'] = sum(avant.values())
    res['elements_apres'] = sum(apres.values())
    res['ecarts'] = [{'element': k, 'avant': a, 'apres': b} for k, a, b in ecarts]
    res['format_apres'] = en_tete(texte2)[0]
    try:
        res['stable'] = to_str(lire(texte2)) == texte2
    except Exception as e:
        res['stable'] = False
        res['erreur_relecture'], res['ou'] = panne(e)
    return res


def phrase(r):
    debut = f"{r['fichier']} (format {r['format']}, écrit par la version {r['fait_par']}) : "
    if not r['lu']:
        return debut + f"PAS LU. {r['erreur']} [{r['ou']}]"
    if not r['reecrit']:
        return debut + f"lu en {r['secondes']} s, mais PAS RÉÉCRIT. {r['erreur']} [{r['ou']}]"
    if r['ecarts']:
        perte = f"{len(r['ecarts'])} sortes d'éléments changent de nombre : " + ', '.join(
            f"{e['element']} {e['avant']} → {e['apres']}" for e in r['ecarts'][:15])
        if len(r['ecarts']) > 15:
            perte += ', ...'
    else:
        perte = "rien de perdu ni d'ajouté"
    stable = 'stable' if r['stable'] else 'PAS stable' + (f" ({r['erreur_relecture']})" if 'erreur_relecture' in r else '')
    return (debut + f"lu en {r['secondes']} s. Aller-retour : {perte} "
            f"({r['elements_avant']} éléments avant, {r['elements_apres']} après) ; réécriture {stable} ; "
            f"format après : {r['format_apres']}.")


def metadonnees(racine):
    """Ce que le portail d'EDeA montrerait d'un module : surface, couches, nombre de pièces."""
    lignes = []
    try:
        from edea.metadata import Project      # 0.8.4 : pas dans edea.kicad.project (essai du 25/10/2026)
    except Exception as e:
        return [f"Fiche de module : pas d'accès à Project ({panne(e)[0]})"]
    for pro in sorted(racine.glob('*/carte.kicad_pro')):
        try:
            m = Project(str(pro)).metadata
            m = m.model_dump() if hasattr(m, 'model_dump') else dict(m)
            garde = {k: v for k, v in m.items() if k != 'parts'}
            lignes.append(f"Fiche de module {pro.parent.name} : {garde}")
        except Exception as e:
            erreur, ou = panne(e)
            lignes.append(f"Fiche de module {pro.parent.name} : PAS FAITE. {erreur} [{ou}]")
    return lignes


def main():
    racine, sortie = Path(sys.argv[1]), Path(sys.argv[2])
    sortie.mkdir(parents=True, exist_ok=True)
    print(f"EDeA {version_paquet('edea')}, Python {sys.version.split()[0]}\n")
    fichiers = sorted(p for p in racine.rglob('*') if p.suffix in ('.kicad_sch', '.kicad_pcb')
                      and not any(c in p.parts for c in COPIES))
    resultats = [essayer(p, racine, sortie) for p in fichiers]
    for r in resultats:
        print(phrase(r))
    print()
    for ligne in metadonnees(racine):
        print(ligne)
    lus = sum(r['lu'] for r in resultats)
    intacts = sum(1 for r in resultats if r.get('reecrit') and not r['ecarts'] and r['stable'])
    print(f"\nBilan : {lus} fichiers lus sur {len(resultats)} ; {intacts} réécrits sans rien perdre.")
    (sortie / 'resume.json').write_text(json.dumps(resultats, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
