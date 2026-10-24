"""Mesures guidées : le plan de test, mesure par mesure, au clavier et au lecteur d'écran.
Pour chaque mesure, le script dit où mettre les pointes (numéros des bornes du banc de test : borne n = sortie TPn,
« masse » = entonnoir carré), lit la valeur, dit si elle est bonne, et range tout dans un fichier daté.
La valeur vient du multimètre par sigrok (logiciel libre, beaucoup de multimètres reliés par USB ou série), si on donne
son pilote ; sinon on la tape (« 4,98 », « 0,3 », « 12k » pour 12 kΩ, « ol » pour circuit ouvert).
Les valeurs attendues sont dans un fichier par carte (cartes/NOM-mesures.json), tirées de son plan de test.
Usage : python3 mesures_guidees.py cartes/radio-v4-mesures.json dossier_resultats/ [--multimetre PILOTE[:conn=PORT]]
        (liste des pilotes : sigrok-cli -L ; par exemple « uni-t-ut61e-ser:conn=/dev/ttyUSB0 »)"""
import argparse, json, os, re, subprocess, time

p = argparse.ArgumentParser(description='Mesures guidées du plan de test.')
p.add_argument('mesures'); p.add_argument('dossier')
p.add_argument('--multimetre', help='pilote sigrok du multimètre, avec ses réglages (sigrok-cli -L)')
a = p.parse_args()
D = json.load(open(a.mesures, encoding='utf-8'))
UNITE = {'ohm': 'Ω', 'V': 'V'}
PREFIXES = {'p': 1e-12, 'n': 1e-9, 'µ': 1e-6, 'u': 1e-6, 'm': 1e-3, '': 1, 'k': 1e3, 'M': 1e6}


def dire(texte=''):
    print(texte, flush=True)


def demander(question):
    return input(question + ' ').strip()


def lire_sigrok(grandeur):
    """Une mesure du multimètre par sigrok-cli, ramenée en volts ou en ohms. None si rien de lisible ou mauvais calibre."""
    cmd = ['sigrok-cli', '--driver', a.multimetre, '--samples', '1', '-O', 'analog']
    for essai in range(3):
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        m = next((m for l in r.stdout.splitlines() for m in [re.search(r':\s*(-?[\d.]+|inf|-inf|nan)\s*([pnµumkM]?)(V|Ω|ohm)', l)] if m), None)
        if m is None:
            dire('  (sigrok n\'a rien rendu de lisible : ' + (r.stderr.strip().splitlines() or ['?'])[-1] + ')')
            return None
        unite = 'V' if m.group(3) == 'V' else 'ohm'
        if unite == grandeur:
            v = float(m.group(1))
            return v * PREFIXES[m.group(2)]
        dire(f"  Le multimètre mesure en {UNITE[unite]} : le mettre en {UNITE[grandeur]}.")
        demander('  Entrée quand c\'est fait :')
    return None


def lire_clavier(grandeur):
    while True:
        s = demander(f"  Tape la valeur lue, en {UNITE[grandeur]} (« 12k » pour 12 000, « ol » si le multimètre affiche OL) :")
        s = s.lower().replace(',', '.').replace(' ', '').replace('ω', '').replace('ohm', '').replace('v', '')
        if s in ('ol', 'o.l', '0l', '0.l', 'inf', 'ouvert'):
            return float('inf')
        m = re.fullmatch(r'(-?[\d.]+)([pnµumkM]?)', s.replace('meg', 'M'))
        if m:
            try:
                return float(m.group(1)) * PREFIXES[m.group(2)]
            except ValueError:
                pass
        dire('  Je n\'ai pas compris ce nombre, on recommence.')


def texte_valeur(v, grandeur):
    if v == float('inf'):
        return 'circuit ouvert'
    if grandeur == 'ohm' and v >= 1000:
        return f"{v / 1000:.2f} kΩ".replace('.', ',')
    return f"{v:.3g} {UNITE[grandeur]}".replace('.', ',')


def attendu(m):
    u = UNITE[m['grandeur']]
    if 'min' in m and 'max' in m:
        return f"entre {str(m['min']).replace('.', ',')} et {str(m['max']).replace('.', ',')} {u}"
    if 'min' in m:
        return f"au-dessus de {str(m['min']).replace('.', ',')} {u}"
    return f"en dessous de {str(m['max']).replace('.', ',')} {u}"


os.makedirs(a.dossier, exist_ok=True)
fichier = os.path.join(a.dossier, 'mesures-' + time.strftime('%Y-%m-%d-%H%M') + '.md')
lignes = [f"# Mesures guidées — {D['carte']}", '', f"Le {time.strftime('%d/%m/%Y à %H:%M')}. Valeurs attendues : {D['source']}",
          f"Lecture : {'multimètre par sigrok (' + a.multimetre + ')' if a.multimetre else 'tapée au clavier'}.", '',
          '| Étape | Bornes | Ce qu\'on vérifie | Attendu | Lu | Résultat |', '|---|---|---|---|---|---|']
dire(f"MESURES GUIDÉES — {D['carte']}")
dire("À chaque mesure : mettre les pointes dans les entonnoirs annoncés, puis Entrée. « q » puis Entrée pour arrêter.")
mauvais, arret = 0, False
for e in D['etapes']:
    dire(); dire(e['titre'].upper()); dire('  ' + e['consigne'])
    if demander('  Entrée quand c\'est prêt (q pour arrêter) :').lower() == 'q':
        break
    pas_bon_ici = 0
    for i, m in enumerate(e['mesures'], 1):
        b1, b2 = m['bornes']
        dire(f"  Mesure {i} sur {len(e['mesures'])} : {m['sens']}.")
        if demander(f"  Pointe rouge dans l'entonnoir {b1}, pointe noire dans l'entonnoir {b2}. Entrée :").lower() == 'q':
            arret = True
            break
        v = lire_sigrok(m['grandeur']) if a.multimetre else None
        if v is None:
            v = lire_clavier(m['grandeur'])
        bon = (v >= m.get('min', float('-inf'))) and (v <= m.get('max', float('inf')))
        dire(f"  Lu : {texte_valeur(v, m['grandeur'])}. Attendu : {attendu(m)}. {'BON.' if bon else 'PAS BON.'}")
        lignes.append(f"| {e['titre'].split(' :')[0]} | {b1} – {b2} | {m['sens']} | {attendu(m)} | {texte_valeur(v, m['grandeur'])} | {'bon' if bon else '**PAS BON**'} |")
        pas_bon_ici += not bon
    mauvais += pas_bon_ici
    if arret:
        break
    if pas_bon_ici and e.get('arret_si_pas_bon'):
        dire(f"  {pas_bon_ici} mesure(s) pas bonne(s) à cette étape : le plan de test dit de s'arrêter là, et de noter ce qu'on a trouvé.")
        if demander('  Continuer quand même ? (o ou n) :').lower() not in ('o', 'oui'):
            break
lignes += ['', f"Bilan : {mauvais} mesure(s) pas bonne(s)." if mauvais else 'Bilan : toutes les mesures faites sont bonnes.']
open(fichier, 'w', encoding='utf-8').write('\n'.join(lignes) + '\n')
dire(); dire(lignes[-1]); dire(f"Résultats rangés dans : {fichier}")
