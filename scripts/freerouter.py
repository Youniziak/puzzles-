"""Chaîne puzzle, étape 2 — « router ce qui manque » avec Freerouting, puis contrôle par KiCad 10.
1. KiCad remplit les plans et dit, par son contrôle, quels réseaux sont incomplets.
2. KiCad écrit le fichier pour Freerouting (Specctra DSN), avec ses classes de réseaux (largeur des alimentations) ;
   les pistes des blocs, verrouillées, y sont « fixes ». Un plan d'alimentation incomplet, coupé en îlots, est retiré
   le temps de l'export : Freerouting relie alors ses broches par des pistes.
3. Freerouting trace, sans son « optimisation » après coup.
4. KiCad reprend le résultat (ImportSpecctraSES). On ne garde le cuivre de Freerouting que sur les réseaux incomplets,
   puis on enlève les bouts de piste qui ne mènent nulle part.
5. S'il manque encore une liaison, nouveau passage (3 au plus, réglable : « routage / passages_max » dans les règles),
   en repartant du précédent : les alimentations encore incomplètes reçoivent la largeur minimale que demande leur courant
   (au lieu de la largeur confortable), ce qui laisse plus de place. Freerouting ne donne jamais deux fois le même résultat.
Usage : python3 freerouter.py cartes/ma-carte.json dossier_projet/carte.kicad_pcb chemin/freerouting.jar"""
import json, math, re, subprocess, sys
from collections import Counter
import pcbnew
from description import Carte

CARTE = Carte(sys.argv[1])
PCB, JAR = sys.argv[2], sys.argv[3]
BASE = PCB[:-len('.kicad_pcb')]

def controle(fichier_json, severite='error', sauver=False):
    cmd = ['kicad-cli', 'pcb', 'drc', '--format', 'json', f'--severity-{severite}', '--output', fichier_json, PCB]
    if severite == 'error':
        cmd.insert(3, '--refill-zones')
    if sauver:
        cmd.insert(3, '--save-board')
    subprocess.run(cmd, capture_output=True, check=True)
    return json.load(open(fichier_json))

def incomplets(d):
    return sorted({m.group(1) for u in d['unconnected_items'] for i in u['items']
                   for m in [re.search(r'\[([^\]]+)\]', i['description'])] if m})

d = controle(BASE + '-controle-avant-routage.json', sauver=True)
a_router = incomplets(d)
print(f"Réseaux incomplets confiés à Freerouting ({len(d['unconnected_items'])} liaisons) :", ', '.join(a_router) or 'aucun')

board = pcbnew.LoadBoard(PCB)

def passage(numero):
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    coupes = [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetname() in a_router
              and z.GetFilledPolysList(z.GetLayer()).OutlineCount() > 1]
    for z in coupes:
        board.Remove(z)
        print(f'Plan {z.GetNetname()} ({z.GetLayerName()}) coupé en îlots : laissé de côté pour Freerouting, qui tracera des pistes à la place')
    assert pcbnew.ExportSpecctraDSN(board, BASE + '.dsn'), "export DSN impossible"
    for z in coupes:
        board.Add(z)

    cmd = ['java', '-jar', JAR, '--gui.enabled=false', '--usage_and_diagnostic_data.disable_analytics=true',
           '--api_server.enabled=false', '--router.optimizer.enabled=false', '-mp', '30', '-de', BASE + '.dsn', '-do', BASE + '.ses']
    with open(BASE + f'-freerouting-{numero}.log', 'w') as log:
        subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, timeout=1500, check=True)
    passes = [l for l in open(BASE + f'-freerouting-{numero}.log') if 'pass #' in l]
    print(f'Freerouting (passage {numero}) :', len(passes), 'passes' + (' ; score final ' + passes[-1].split('score of')[1].split(',')[0].strip() if passes else ''))

    avant = len(board.GetTracks())
    assert pcbnew.ImportSpecctraSES(board, BASE + '.ses'), "KiCad n'a pas pu relire le résultat de Freerouting"
    # KiCad reprend tout le fichier de Freerouting, y compris des fils sur des réseaux déjà complets :
    # on ne garde le travail de Freerouting que sur les réseaux incomplets.
    hors_sujet = [t for t in board.GetTracks() if not t.IsLocked() and t.GetNetname() not in a_router]
    for t in hors_sujet:
        board.Delete(t)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board)
    print(f'KiCad a repris le travail de Freerouting : {avant} → {len(board.GetTracks())} pistes et vias '
          f'({len(hors_sujet)} fils sur des réseaux déjà complets écartés)')

    # Ménage : un bout de piste dont une extrémité ne touche rien (« track_dangling ») ne relie rien ; l'enlever ne coupe rien.
    # On n'enlève que des pistes de Freerouting (non verrouillées) ; le contrôle final vérifie qu'aucune liaison ne manque.
    enleves, restants = 0, 0
    for _ in range(6):                     # enlever un bout peut en découvrir un autre derrière : on recommence
        ids = {i['uuid'] for v in controle(BASE + '-menage.json', 'warning')['violations'] if v['type'] == 'track_dangling' for i in v['items']}
        ids |= {i['uuid'] for v in json.load(open(BASE + '-menage.json'))['violations'] if v['type'] == 'via_dangling' for i in v['items']}
        a_enlever = [t for t in board.GetTracks() if t.m_Uuid.AsString() in ids and not t.IsLocked() and t.GetClass() in ('PCB_TRACK', 'PCB_VIA')]
        restants = len(ids) - len(a_enlever)
        if not a_enlever:
            break
        for t in a_enlever:
            board.Delete(t)
        enleves += len(a_enlever)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(PCB, board)
    print(f'Ménage : {enleves} bout(s) de piste inutile(s) enlevé(s) ; restent {restants} signalé(s) (pistes des blocs, verrouillées)')

PASSAGES_MAX = CARTE.regles.get('routage', {}).get('passages_max', 3)
if a_router:
    passage(1)
    for numero in range(2, PASSAGES_MAX + 1):
        restants = incomplets(controle(BASE + '-controle.json'))
        if not restants:
            break
        ns = board.GetDesignSettings().m_NetSettings
        etroites = []
        for nom in restants:
            if nom in CARTE.courants and ns.HasNetclass(f'Alim_{nom}'):
                w = math.ceil(CARTE.largeur_mini(CARTE.courants[nom]) / 0.05 - 1e-9) * 0.05
                ns.GetNetClassByName(f'Alim_{nom}').SetTrackWidth(pcbnew.FromMM(w))
                etroites.append(f'{nom} {w:.2f} mm')
        ns.RecomputeEffectiveNetclasses()
        board.SynchronizeNetsAndNetClasses(False)
        print(f"Encore incomplets : {', '.join(restants)}. Passage {numero} sur {PASSAGES_MAX}, en repartant du précédent"
              + (f" ; largeur minimale pour : {', '.join(etroites)}" if etroites else ''))
        passage(numero)

d = controle(BASE + '-controle.json')
print('Contrôle KiCad 10 :', dict(Counter(v['type'] for v in d['violations'])) or 'aucune erreur',
      '| liaisons manquantes :', len(d['unconnected_items']))
sys.exit(1 if d['unconnected_items'] else 0)
