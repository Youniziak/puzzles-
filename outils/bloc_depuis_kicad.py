"""Prendre un bloc dans une carte KiCad libre et déjà fabriquée (par exemple une carte d'Olimex), avec son routage
éprouvé : rien n'est routé de nouveau.
1. Sur une copie de la carte, un contour est tracé autour de la zone (KiKit en a besoin), puis KiKit (kikit separate)
   la découpe : composants, pistes, vias et plans qui sont dedans.
2. On ne garde que les composants demandés ; on enlève les pistes, vias et plans des autres réseaux, puis, avec le
   contrôle de KiCad, les bouts de piste et les vias qui ne mènent plus nulle part.
3. Les réseaux sont renommés : ceux de l'interface prennent le nom qu'ils ont sur la carte d'accueil (VBUS, 3V3,
   GND...), les réseaux internes un nom propre au bloc (préfixe).
4. Le bloc est ramené au coin (0, 0). Une fiche bloc.json garde la source, la licence et l'attribution : la CERN-OHL
   demande de garder la mention de l'auteur.
Usage : python3 bloc_depuis_kicad.py source.kicad_pcb x0,y0,x1,y1 REF1,REF2,... dossier_sortie --kikit chemin/kikit
        --prefixe NOM [--reseaux ANCIEN=NOUVEAU,...] [--interface NOM1,NOM2,...] [--description TEXTE]
        [--source-url URL] [--licence NOM] [--attribution TEXTE]
Les coordonnées de la zone sont celles de KiCad, en mm, dans la carte source."""
import argparse, json, os, re, subprocess, sys, tempfile
import pcbnew

p = argparse.ArgumentParser(description="Prendre un bloc, routage compris, dans une carte KiCad libre.")
p.add_argument('source'); p.add_argument('zone'); p.add_argument('garder'); p.add_argument('sortie')
p.add_argument('--kikit', required=True)
p.add_argument('--prefixe', required=True, help='préfixe des réseaux internes du bloc (par exemple DCDC)')
p.add_argument('--reseaux', default='', help="ANCIEN=NOUVEAU,... : réseaux renommés (interface ou internes)")
p.add_argument('--interface', default='', help="réseaux du bloc qui se relient à la carte d'accueil (noms nouveaux)")
p.add_argument('--description', default='')
p.add_argument('--source-url', default='')
p.add_argument('--licence', default='')
p.add_argument('--attribution', default='')
a = p.parse_args()
x0, y0, x1, y1 = (float(v) for v in a.zone.split(','))
garder = set(a.garder.split(','))
renommer = dict(kv.split('=', 1) for kv in a.reseaux.split(',') if kv)
os.makedirs(a.sortie, exist_ok=True)
SORTIE = os.path.join(a.sortie, 'bloc.kicad_pcb')
mm, MM = pcbnew.ToMM, pcbnew.FromMM

# ---------- 1. contour sur une copie, puis découpe par KiKit
with tempfile.TemporaryDirectory() as tmp:
    b = pcbnew.LoadBoard(a.source)
    r = pcbnew.PCB_SHAPE(b)
    r.SetShape(pcbnew.SHAPE_T_RECT)
    r.SetStart(pcbnew.VECTOR2I(MM(x0), MM(y0)))
    r.SetEnd(pcbnew.VECTOR2I(MM(x1), MM(y1)))
    r.SetLayer(pcbnew.Edge_Cuts)
    r.SetWidth(MM(0.05))
    b.Add(r)
    copie = os.path.join(tmp, 'copie.kicad_pcb')
    b.Save(copie)
    marge = 0.3
    source = f'type: rectangle; tlx: {x0 - marge}mm; tly: {y0 - marge}mm; brx: {x1 + marge}mm; bry: {y1 + marge}mm'
    k = subprocess.run([a.kikit, 'separate', '--source', source, copie, SORTIE], capture_output=True, text=True)
    if k.returncode or not os.path.exists(SORTIE):
        sys.exit("KiKit n'a pas découpé la zone : " + (k.stdout + k.stderr).strip().splitlines()[-1])

# ---------- 2. garder les composants demandés, et le cuivre de leurs réseaux
b = pcbnew.LoadBoard(SORTIE)
for f in list(b.GetFootprints()):
    if f.GetReference() not in garder:
        b.Delete(f)
manque = garder - {f.GetReference() for f in b.GetFootprints()}
if manque:
    sys.exit(f"Composants absents de la zone : {', '.join(sorted(manque))}")
reseaux = {pad.GetNetname() for f in b.GetFootprints() for pad in f.Pads()} - {''}
for t in list(b.GetTracks()):
    if t.GetNetname() not in reseaux:
        b.Delete(t)
for z in list(b.Zones()):
    if not z.GetIsRuleArea() and z.GetNetname() not in reseaux:
        b.Delete(z)
for d in list(b.GetDrawings()):          # logos et textes de la carte d'origine : seul le contour reste
    if d.GetLayer() != pcbnew.Edge_Cuts:
        b.Delete(d)
b.Save(SORTIE)

# Ménage avec le contrôle de KiCad : un bout de piste ou une via qui ne touche plus rien ne relie rien.
enleves = 0
for _ in range(8):
    rapport = os.path.join(a.sortie, 'menage.json')
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-warning', '--output', rapport, SORTIE],
                   capture_output=True, check=True)
    ids = {i['uuid'] for v in json.load(open(rapport))['violations'] if v['type'] in ('track_dangling', 'via_dangling')
           for i in v['items']}
    os.remove(rapport)
    a_enlever = [t for t in b.GetTracks() if t.m_Uuid.AsString() in ids]
    if not a_enlever:
        break
    for t in a_enlever:
        b.Delete(t)
    enleves += len(a_enlever)
    b.Save(SORTIE)

# ---------- 3. renommer les réseaux
def nom_interne(nom):
    """« Net-(L1-Pad1) » → « PREFIXE_L1_1 » ; un nom déjà lisible garde son nom, avec le préfixe."""
    m = re.match(r'Net-\((\w+?)-Pad(\w+)\)$', nom)
    propre = f'{m.group(1)}_{m.group(2)}' if m else re.sub(r'[^A-Za-z0-9]+', '_', nom).strip('_')
    return f'{a.prefixe}_{propre}'

nouveaux = {nom: renommer.get(nom, nom_interne(nom)) for nom in sorted(reseaux)}
cache = {}
def reseau(nom):
    if nom not in cache:
        n = b.FindNet(nom)
        if not n:
            n = pcbnew.NETINFO_ITEM(b, nom)
            b.Add(n)
        cache[nom] = n
    return cache[nom]
for f in b.GetFootprints():
    for pad in f.Pads():
        if pad.GetNetname():
            pad.SetNet(reseau(nouveaux[pad.GetNetname()]))
for t in b.GetTracks():
    t.SetNet(reseau(nouveaux[t.GetNetname()]))
for z in b.Zones():
    if z.GetNetname():
        z.SetNet(reseau(nouveaux[z.GetNetname()]))

# ---------- 4. ramener le bloc au coin (0, 0)
bb = b.GetBoardEdgesBoundingBox()
decalage = pcbnew.VECTOR2I(-bb.GetLeft(), -bb.GetTop())
for f in b.GetFootprints():
    f.Move(decalage)
for t in b.GetTracks():
    t.Move(decalage)
for z in b.Zones():
    z.Move(decalage)
for d in b.GetDrawings():
    d.Move(decalage)
b.Save(SORTIE)

pistes = [t for t in b.GetTracks() if t.GetClass() != 'PCB_VIA']
vias = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA']
interface = [n for n in a.interface.split(',') if n] or sorted(v for v in nouveaux.values() if not v.startswith(a.prefixe + '_'))
fiche = {
    'nom': os.path.basename(os.path.normpath(a.sortie)),
    'type': 'kicad',
    'description': a.description,
    'taille': [round(mm(bb.GetWidth()), 2), round(mm(bb.GetHeight()), 2)],
    'interface': interface,
    'source': {'carte': os.path.basename(a.source), 'url': a.source_url, 'zone_mm': [x0, y0, x1, y1],
               'reseaux_renommes': nouveaux},
    'licence': a.licence,
    'attribution': a.attribution,
    'composants': [{'repere': f.GetReference(), 'valeur': f.GetValue(), 'empreinte': f.GetFPIDAsString(),
                    'reseaux': {pad.GetNumber(): pad.GetNetname() for pad in f.Pads()}}
                   for f in sorted(b.GetFootprints(), key=lambda f: f.GetReference())],
    'routage': {'pistes': len(pistes), 'vias': len(vias), 'plans': len(list(b.Zones()))},
}
json.dump(fiche, open(os.path.join(a.sortie, 'bloc.json'), 'w'), ensure_ascii=False, indent=1)
print(f"Bloc {fiche['nom']} : {fiche['taille'][0]} × {fiche['taille'][1]} mm ; {len(fiche['composants'])} composants "
      f"({', '.join(c['repere'] for c in fiche['composants'])}) ; {len(pistes)} pistes, {len(vias)} vias, "
      f"{fiche['routage']['plans']} plans ; {enleves} bouts de piste ou vias inutiles enlevés")
print('Réseaux :', ', '.join(f'{k} → {v}' for k, v in nouveaux.items()))
