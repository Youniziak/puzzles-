"""Chaîne puzzle, étape 1 — « assembler » : recolle les blocs routés par EasyGerber en une seule carte KiCad 10.
- Chaque composant reçoit sa VRAIE empreinte (bibliothèque faite par easyeda2kicad), posée là où EasyGerber l'a mise ;
  chaque pastille prend le réseau de la pastille EasyGerber au même endroit (écart toléré 0,05 mm), sinon c'est signalé.
- Les pistes et vias des blocs sont reprises et verrouillées, sauf celles qui sont fautives (trop près d'un autre réseau,
  ou trop étroites pour leur courant) : Freerouting les retracera.
- Plans d'alimentation des blocs, plans de masse sur toute la carte, zones sans cuivre des blocs (antenne…).
- Trous de fixation (s'ils sont décrits) : trous M3, métallisés et reliés à la masse par les plans, ou non métallisés ;
  « sur la carte seulement » (hors schéma, liste des pièces et placement).
- Le projet KiCad reçoit les règles du fabricant et une classe par alimentation (largeur selon le courant) :
  KiCad les transmet lui-même à Freerouting.
Usage : python3 assembler.py cartes/ma-carte.json dossier_projet/"""
import json, math, os, shutil, sys
import pcbnew
from shapely.geometry import LineString, Point, box
from shapely.affinity import rotate, translate
from description import Carte, champs_piece

CARTE = Carte(sys.argv[1])
SORTIE = sys.argv[2]
os.makedirs(SORTIE, exist_ok=True)
PCB = os.path.join(SORTIE, 'carte.kicad_pcb')
REGLES = CARTE.regles
W, H, R = CARTE.largeur, CARTE.hauteur, CARTE.rayon

mm = pcbnew.FromMM
def V(x, y):                       # EasyGerber : y vers le haut ; KiCad : y vers le bas
    return pcbnew.VECTOR2I(mm(x), mm(-y))

def forme_pastille(q):
    w, h = q['width'], q['height']
    if q['shape'] == 'circle':
        return Point(0, 0).buffer(w / 2, 32)
    if q['shape'] == 'oval':
        r = min(w, h) / 2
        return box(-w / 2 + r, -h / 2 + r, w / 2 - r, h / 2 - r).buffer(r, 16) if w != h else Point(0, 0).buffer(r, 32)
    return box(-w / 2, -h / 2, w / 2, h / 2)

def pistes_fautives(b):
    """Pistes d'un bloc à moins de l'écart minimal d'un autre réseau, ou plus étroites que leur courant ne le demande."""
    d = b.design
    clr = d['designRules']['minClearance'] - 0.005
    autres = []
    for p in d['parts']:
        for q in p['pads']:
            if q['type'] == 'npth':
                continue
            g = translate(rotate(translate(rotate(forme_pastille(q), q.get('rotation', 0), origin=(0, 0)), q['x'], q['y']),
                                 p['rotation'], origin=(0, 0)), p['x'], p['y'])
            autres.append((q.get('netName') or f"libre_{p['id']}_{q['id']}", ['F.Cu'] if q['type'] == 'smd' else ['F.Cu', 'B.Cu'], g))
    for v in d['vias']:
        autres.append((v['net'], ['F.Cu', 'B.Cu'], Point(v['x'], v['y']).buffer(v['outerDiameter'] / 2, 16)))
    geo = [(t, LineString([(pt['x'], pt['y']) for pt in t['points']])) for t in d['traces']]
    for t, ligne in geo:
        autres.append((t['net'], [t['layer']], ligne.buffer(t['widthProfile']['widthMm'] / 2, 8)))
    mauvaises = set()
    for t, ligne in geo:
        i_a = b.courants_locaux.get(t['net'])
        if i_a and t['widthProfile']['widthMm'] < CARTE.largeur_mini(i_a) - 0.01 and ligne.length > 2:
            mauvaises.add(t['id'])
        g = ligne.buffer(t['widthProfile']['widthMm'] / 2, 8)
        if any(n != t['net'] and t['layer'] in lays and g.distance(o) < clr for n, lays, o in autres):
            mauvaises.add(t['id'])
    return mauvaises

board = pcbnew.BOARD()
board.SetCopperLayerCount(2)
ds = board.GetDesignSettings()
k = REGLES['kicad']
ds.m_MinClearance = mm(k['min_clearance']); ds.m_TrackMinWidth = mm(k['min_track_width'])
ds.m_MinThroughDrill = mm(k['min_through_hole_diameter']); ds.m_CopperEdgeClearance = mm(k['min_copper_edge_clearance'])
ds.m_HoleClearance = mm(k['min_hole_clearance']); ds.m_ViasMinSize = mm(k['min_via_diameter'])
cd = {k_: v for k_, v in REGLES['classe_par_defaut'].items() if k_ != 'note'}
nc = ds.m_NetSettings.GetDefaultNetclass()
nc.SetClearance(mm(cd['clearance'])); nc.SetTrackWidth(mm(cd['track_width'])); nc.SetViaDiameter(mm(cd['via_diameter'])); nc.SetViaDrill(mm(cd['via_drill']))

# Contour : rectangle à coins arrondis
def seg(a, b):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetStart(V(*a)); s.SetEnd(V(*b)); s.SetWidth(mm(0.05)); board.Add(s)
def arc(c, debut, fin):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_ARC); s.SetLayer(pcbnew.Edge_Cuts)
    milieu = (c[0] + (debut[0] + fin[0] - 2 * c[0]) / math.sqrt(2), c[1] + (debut[1] + fin[1] - 2 * c[1]) / math.sqrt(2))
    s.SetArcGeometry(V(*debut), V(*milieu), V(*fin)); s.SetWidth(mm(0.05)); board.Add(s)
seg((R, 0), (W - R, 0)); seg((W, R), (W, H - R)); seg((W - R, H), (R, H)); seg((0, H - R), (0, R))
if R > 0:
    arc((W - R, R), (W - R, 0), (W, R)); arc((W - R, H - R), (W, H - R), (W - R, H))
    arc((R, H - R), (R, H), (0, H - R)); arc((R, R), (0, R), (R, 0))

nets = {}
def net(nom):
    if not nom:
        return None
    if nom not in nets:
        n = pcbnew.NETINFO_ITEM(board, nom); board.Add(n); nets[nom] = n
    return nets[nom]
net(CARTE.masse)

LAY = {'F.Cu': pcbnew.F_Cu, 'B.Cu': pcbnew.B_Cu}
COURANTS = CARTE.courants
problemes, exclues_total = [], {}
bib = os.path.join(CARTE.empreintes, CARTE.nom_bib + '.pretty')
for b in CARTE.blocs:
    d = b.design
    for p in d['parts']:
        px, py = b.point(p['x'], p['y'])
        ref = CARTE.repere(b, p['id'])
        if p['lcscPartNumber'] not in CARTE.correspondance:
            problemes.append(f"{b.id}/{p['id']} : pas d'empreinte pour {p['lcscPartNumber']} dans correspondance.json"); continue
        nom_fp = CARTE.correspondance[p['lcscPartNumber']]['empreinte']
        fp = pcbnew.FootprintLoad(bib, nom_fp)
        fp.SetFPID(pcbnew.LIB_ID(CARTE.nom_bib, nom_fp))
        fp.SetReference(ref); fp.SetValue(b.valeurs_locales.get(p['id'], ''))
        for champ, v in champs_piece(p):              # la vraie pièce, pas celle qui a servi à télécharger l'empreinte
            fp.SetField(champ, v)
            fp.GetField(champ).SetVisible(False)
        fp.SetPosition(V(px, py)); fp.SetOrientation(pcbnew.EDA_ANGLE(b.angle(p['rotation']), pcbnew.DEGREES_T))
        if p['id'] in b.bloc.get('non_poses', []):      # sortie en cuivre nu : rien à poser, hors liste des pièces et placement
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM)
        for mdl in fp.Models():
            mdl.m_Filename = f'${{KIPRJMOD}}/lib/{CARTE.nom_bib}.3dshapes/' + os.path.basename(mdl.m_Filename)
        board.Add(fp)
        eg = [(q, *b.pastille(p, q)) for q in p['pads']]
        for pad in fp.Pads():
            x, y = pcbnew.ToMM(pad.GetPosition().x), -pcbnew.ToMM(pad.GetPosition().y)
            q, qx, qy = min(eg, key=lambda e: math.hypot(e[1] - x, e[2] - y))
            if math.hypot(qx - x, qy - y) > 0.05:
                problemes.append(f"{b.id}/{p['id']} pastille {pad.GetNumber() or '(sans numéro)'} : pas de pastille EasyGerber au même endroit")
                continue
            if q['type'] == 'npth' or (pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and not pad.GetNumber() and pad.GetSize(pcbnew.F_Cu).x <= pad.GetDrillSize().x):
                pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH); pad.SetLayerSet(pad.UnplatedHoleMask()); continue
            n = net(CARTE.reseau(b, q.get('netName')))
            if n:
                pad.SetNet(n)
    exclues = pistes_fautives(b); exclues_total[b.id] = sorted(exclues)
    for t in d['traces']:
        if t['id'] in exclues:
            continue
        pts = t['points']
        for a_, b_ in zip(pts, pts[1:]):
            tr = pcbnew.PCB_TRACK(board)
            tr.SetStart(V(*b.point(a_['x'], a_['y']))); tr.SetEnd(V(*b.point(b_['x'], b_['y'])))
            tr.SetWidth(mm(t['widthProfile']['widthMm'])); tr.SetLayer(LAY[t['layer']]); tr.SetNet(net(CARTE.reseau(b, t['net'])))
            tr.SetLocked(True); board.Add(tr)
    for v in d['vias']:
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(V(*b.point(v['x'], v['y']))); via.SetWidth(mm(v['outerDiameter'])); via.SetDrill(mm(v['drillDiameter']))
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); via.SetNet(net(CARTE.reseau(b, v['net']))); via.SetLocked(True)
        board.Add(via)
    for z in d['zones']:
        nom = CARTE.reseau(b, z['net'])
        if nom == CARTE.masse:
            continue
        zone = pcbnew.ZONE(board)
        zone.SetLayer(LAY[z['layer']]); zone.SetNet(net(nom)); zone.SetAssignedPriority(2)
        ol = zone.Outline(); ol.NewOutline()
        for pt in z['points']:
            x, y = b.point(pt['x'], pt['y'])
            ol.Append(mm(x), mm(-y))
        i_a = COURANTS.get(nom)
        zone.SetLocalClearance(mm(REGLES['plans']['ecart_alimentation']))
        zone.SetMinThickness(mm(round(max(0.15, CARTE.largeur_mini(i_a)) if i_a else 0.15, 2)))
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        board.Add(zone)

retrait = REGLES['plans']['retrait_du_bord']
for layer in (pcbnew.F_Cu, pcbnew.B_Cu):          # plans de masse sur toute la carte
    zone = pcbnew.ZONE(board)
    zone.SetLayer(layer); zone.SetNet(net(CARTE.masse)); zone.SetAssignedPriority(0)
    ol = zone.Outline(); ol.NewOutline()
    for x, y in ((retrait, retrait), (W - retrait, retrait), (W - retrait, H - retrait), (retrait, H - retrait)):
        ol.Append(mm(x), mm(-y))
    zone.SetLocalClearance(mm(REGLES['plans']['ecart_masse'])); zone.SetMinThickness(mm(REGLES['plans']['epaisseur_min']))
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    board.Add(zone)

T = CARTE.trou
for i, (x, y) in enumerate(CARTE.trous_fixation, 1):            # trous de fixation
    fp = pcbnew.FOOTPRINT(board)
    fp.SetFPID(pcbnew.LIB_ID('MountingHole', f"MountingHole_{T['diametre_trou_mm']}mm{'_Pad' if T['masse'] else ''}"))
    fp.SetReference(f'H{i}'); fp.SetValue(f"Trou de fixation Ø{T['diametre_trou_mm']}")
    pad = pcbnew.PAD(fp); pad.SetNumber('1' if T['masse'] else '')
    pad.SetShape(pcbnew.F_Cu, pcbnew.PAD_SHAPE_CIRCLE); pad.SetDrillShape(pcbnew.PAD_DRILL_SHAPE_CIRCLE)
    pad.SetDrillSize(pcbnew.VECTOR2I(mm(T['diametre_trou_mm']), mm(T['diametre_trou_mm'])))
    if T['masse']:
        pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH); pad.SetLayerSet(pad.PTHMask())
        pad.SetSize(pcbnew.F_Cu, pcbnew.VECTOR2I(mm(T['diametre_cuivre_mm']), mm(T['diametre_cuivre_mm'])))
    else:
        pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH); pad.SetLayerSet(pad.UnplatedHoleMask())
        pad.SetSize(pcbnew.F_Cu, pcbnew.VECTOR2I(mm(T['diametre_trou_mm']), mm(T['diametre_trou_mm'])))
    fp.Add(pad)
    cy_ = pcbnew.PCB_SHAPE(fp); cy_.SetShape(pcbnew.SHAPE_T_CIRCLE); cy_.SetLayer(pcbnew.F_CrtYd)
    cy_.SetCenter(pcbnew.VECTOR2I(0, 0)); cy_.SetEnd(pcbnew.VECTOR2I(mm(T['diametre_cuivre_mm'] / 2 + T['garde_mm']), 0)); cy_.SetWidth(mm(0.05)); fp.Add(cy_)
    fp.SetAttributes(pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    fp.SetPosition(V(x, y))
    board.Add(fp)
    if T['masse']:
        pad.SetNet(net(CARTE.masse))

for raison, (x0, y0, x1, y1) in CARTE.zones_sans_cuivre:   # ni plan, ni piste, ni via
    ka = pcbnew.ZONE(board)
    ka.SetIsRuleArea(True); ka.SetDoNotAllowZoneFills(True); ka.SetDoNotAllowTracks(True); ka.SetDoNotAllowVias(True)
    ka.SetZoneName(raison[:60])
    ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.B_Cu); ka.SetLayerSet(ls)
    ol = ka.Outline(); ol.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        ol.Append(mm(x), mm(-y))
    board.Add(ka)

pcbnew.SaveBoard(PCB, board)

# Projet KiCad : règles du fabricant, classe par défaut, une classe par alimentation (KiCad la transmet à Freerouting)
pro = PCB[:-len('.kicad_pcb')] + '.kicad_pro'
p = json.load(open(pro)) if os.path.exists(pro) else {}
p.setdefault('board', {}).setdefault('design_settings', {}).setdefault('rules', {}).update(k)
ns = p.setdefault('net_settings', {})
classes = ns.setdefault('classes', [{'name': 'Default'}])
defaut = next(c for c in classes if c.get('name') == 'Default')
defaut.update(cd)
ns['classes'] = [defaut]
ns['netclass_patterns'] = []
for nom, i_a in sorted(COURANTS.items()):
    c = dict(defaut); c.update({'name': f'Alim_{nom}', 'track_width': round(CARTE.largeur_classe(i_a), 2)})
    ns['classes'].append(c)
    ns['netclass_patterns'].append({'netclass': f'Alim_{nom}', 'pattern': nom})
json.dump(p, open(pro, 'w'), indent=2)

# Règle en plus, que les réglages de base de KiCad ne savent pas dire : écart entre un trou métallisé (via, broche)
# et le cuivre d'un autre réseau, selon le fabricant. KiCad la relit tout seul (fichier .kicad_dru du projet).
seuil = REGLES['controle']['trou_metallise_cuivre'] - 0.005
open(PCB[:-len('.kicad_pcb')] + '.kicad_dru', 'w').write(
    f'(version 1)\n(rule "trou metallise - cuivre (fabricant)"\n  (constraint hole_clearance (min {seuil:.3f}mm))\n  (condition "A.isPlated()"))\n')

# Bibliothèque d'empreintes copiée dans le projet : le projet s'ouvre seul, n'importe où
for sous in (CARTE.nom_bib + '.pretty', CARTE.nom_bib + '.3dshapes'):
    shutil.copytree(os.path.join(CARTE.empreintes, sous), os.path.join(SORTIE, 'lib', sous), dirs_exist_ok=True)
open(os.path.join(SORTIE, 'fp-lib-table'), 'w').write(
    f'(fp_lib_table\n  (version 7)\n  (lib (name "{CARTE.nom_bib}")(type "KiCad")(uri "${{KIPRJMOD}}/lib/{CARTE.nom_bib}.pretty")(options "")(descr "Empreintes LCSC via easyeda2kicad"))\n)\n')

print(f"assemblé : {CARTE.nom} — {len(CARTE.blocs)} blocs, {len(board.GetFootprints())} composants (vraies empreintes), "
      f"{len(board.GetTracks())} pistes et vias des blocs")
print('alimentations :', ', '.join(f"{n} {i} A → piste de {CARTE.largeur_classe(i):.2f} mm" for n, i in sorted(COURANTS.items())) or 'aucune')
print('zones sans cuivre :', [r for r, _ in CARTE.zones_sans_cuivre] or 'aucune')
print('trous de fixation :', ', '.join(f"H{i} ({x:g} ; {y:g})" for i, (x, y) in enumerate(CARTE.trous_fixation, 1)) or 'aucun')
print('pistes de bloc écartées (Freerouting les retracera) :', {k_: v for k_, v in exclues_total.items() if v} or 'aucune')
print('problèmes de pastilles :', problemes or 'aucun')
sys.exit(1 if problemes else 0)
