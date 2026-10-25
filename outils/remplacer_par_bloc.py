"""Essai : remplacer des composants d'une carte déjà assemblée par un bloc libre (fait par bloc_depuis_kicad.py).
1. On enlève les composants donnés, et toutes les pistes et vias qui passent dans la zone libérée ; puis, avec le
   contrôle de KiCad, les bouts de piste qui menaient à la zone et ne mènent plus nulle part.
2. On pose le bloc (composants, pistes, vias, zones interdites), tourné et centré au point donné. Ses réseaux
   d'interface prennent ceux de la carte (même nom) ; ses réseaux internes sont créés. Ses pistes sont verrouillées :
   Freerouting les gardera telles quelles. Ses repères sont renumérotés après ceux de la carte (U6, L1...).
3. Une mention de la source et de la licence est écrite sur la sérigraphie (la CERN-OHL demande de garder celle de
   l'auteur).
Les fichiers du projet KiCad (règles, empreintes) sont copiés à côté de la nouvelle carte.
Ensuite : scripts/freerouter.py trace ce qui manque, puis KiCad contrôle.
Usage : python3 remplacer_par_bloc.py carte.kicad_pcb dossier_du_bloc carte_sortie.kicad_pcb --retirer U2,C2,C3
        --zone x0,y0,x1,y1 --centre x,y [--rotation 90] --mention TEXTE [--mention-position x,y] [--mention-face F|B]
Les coordonnées sont celles de KiCad, en mm (y vers le bas)."""
import argparse, json, os, re, shutil, subprocess, sys
import pcbnew
from shapely.geometry import LineString, Point, box

p = argparse.ArgumentParser(description="Remplacer des composants d'une carte par un bloc libre (essai).")
p.add_argument('carte'); p.add_argument('bloc'); p.add_argument('sortie')
p.add_argument('--retirer', required=True, help='repères à enlever, séparés par des virgules')
p.add_argument('--zone', required=True, help='x0,y0,x1,y1 : zone libérée, où les pistes sont enlevées')
p.add_argument('--centre', required=True, help='x,y : centre du bloc posé')
p.add_argument('--rotation', type=float, default=0.0, help='en degrés, sens de KiCad')
p.add_argument('--mention', required=True, help='texte de sérigraphie : source et licence du bloc')
p.add_argument('--mention-position', help='x,y du texte (par défaut : sous le bloc)')
p.add_argument('--mention-face', default='B', choices=['F', 'B'], help='face de la mention (B : dessous, par défaut)')
a = p.parse_args()
mm, MM = pcbnew.ToMM, pcbnew.FromMM
x0, y0, x1, y1 = (float(v) for v in a.zone.split(','))
cx, cy = (float(v) for v in a.centre.split(','))
ZONE = box(x0, y0, x1, y1)
os.makedirs(os.path.dirname(os.path.abspath(a.sortie)), exist_ok=True)

# Les fichiers du projet (règles du fabricant, empreintes) suivent la carte : le contrôle de KiCad en a besoin.
dossier, base = os.path.dirname(os.path.abspath(a.carte)), os.path.basename(a.carte)[:-len('.kicad_pcb')]
dest, base_dest = os.path.dirname(os.path.abspath(a.sortie)), os.path.basename(a.sortie)[:-len('.kicad_pcb')]
for ext in ('.kicad_pro', '.kicad_dru'):
    if os.path.exists(os.path.join(dossier, base + ext)):
        shutil.copy(os.path.join(dossier, base + ext), os.path.join(dest, base_dest + ext))
for nom in ('fp-lib-table', 'lib'):
    src = os.path.join(dossier, nom)
    if os.path.isdir(src):
        shutil.copytree(src, os.path.join(dest, nom), dirs_exist_ok=True)
    elif os.path.exists(src):
        shutil.copy(src, os.path.join(dest, nom))

def largeur(t):
    try:
        return mm(t.GetWidth())
    except TypeError:                        # une via, dans KiCad 10, donne sa taille couche par couche
        return mm(t.GetWidth(pcbnew.F_Cu))

def forme(t):
    if t.GetClass() == 'PCB_VIA':
        q = t.GetPosition()
        return Point(mm(q.x), mm(q.y)).buffer(largeur(t) / 2)
    pts = [t.GetStart(), t.GetMid(), t.GetEnd()] if t.GetClass() == 'PCB_ARC' else [t.GetStart(), t.GetEnd()]
    return LineString([(mm(q.x), mm(q.y)) for q in pts]).buffer(largeur(t) / 2)

# ---------- 1. libérer la place
b = pcbnew.LoadBoard(a.carte)
# Les pistes déjà tracées et contrôlées sont verrouillées : Freerouting ne touchera qu'à ce qui manque. Sinon, la
# reprise de son travail par KiCad les efface (constaté le 25/10/2026 : 7 liaisons entre blocs perdues).
for t in b.GetTracks():
    t.SetLocked(True)
retires = []
for ref in a.retirer.split(','):
    f = b.FindFootprintByReference(ref)
    if not f:
        sys.exit(f'Repère {ref} absent de la carte')
    retires.append(f'{ref} ({f.GetValue()})')
    b.Delete(f)
enlevees = [t for t in b.GetTracks() if forme(t).intersects(ZONE)]
for t in enlevees:
    b.Delete(t)
pcbnew.SaveBoard(a.sortie, b)

# Bouts de piste qui menaient à la zone (à moins de 3 mm) et ne touchent plus rien : enlevés, verrouillés ou non.
pres = ZONE.buffer(3.0)
bouts = 0
for _ in range(8):
    rapport = a.sortie[:-len('.kicad_pcb')] + '-menage-pose.json'
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-warning', '--output', rapport, a.sortie],
                   capture_output=True, check=True)
    ids = {i['uuid'] for v in json.load(open(rapport))['violations'] if v['type'] in ('track_dangling', 'via_dangling')
           for i in v['items']}
    os.remove(rapport)
    a_enlever = [t for t in b.GetTracks() if t.m_Uuid.AsString() in ids and forme(t).intersects(pres)]
    if not a_enlever:
        break
    for t in a_enlever:
        b.Delete(t)
    bouts += len(a_enlever)
    pcbnew.SaveBoard(a.sortie, b)

# ---------- 2. poser le bloc
blk = pcbnew.LoadBoard(os.path.join(a.bloc, 'bloc.kicad_pcb'))
fiche = json.load(open(os.path.join(a.bloc, 'bloc.json')))
c0 = blk.GetBoardEdgesBoundingBox().GetCenter()
cible = pcbnew.VECTOR2I(MM(cx), MM(cy))
angle = pcbnew.EDA_ANGLE(a.rotation, pcbnew.DEGREES_T)
cache = {}
def reseau(nom):
    if nom not in cache:
        n = b.FindNet(nom)
        if not n:
            n = pcbnew.NETINFO_ITEM(b, nom)
            b.Add(n)
        cache[nom] = n
    return cache[nom]

pris = {f.GetReference() for f in b.GetFootprints()}
def repere_libre(ref):
    prefixe = re.match(r'[A-Za-z_]+', ref).group(0)
    n = 1
    while f'{prefixe}{n}' in pris:
        n += 1
    pris.add(f'{prefixe}{n}')
    return f'{prefixe}{n}'

def poser(objet):
    objet.Rotate(c0, angle)
    objet.Move(cible - c0)

reperes = {}
hauteur_min = b.GetDesignSettings().m_MinSilkTextHeight     # les textes d'Olimex font 0,76 mm, la règle 0,8
for f in sorted(blk.GetFootprints(), key=lambda f: f.GetReference()):
    g = pcbnew.FOOTPRINT(f)
    poser(g)
    reperes[f.GetReference()] = repere_libre(f.GetReference())
    g.SetReference(reperes[f.GetReference()])
    for champ in (g.Reference(), g.Value()):
        if champ.GetTextHeight() < hauteur_min:
            champ.SetTextSize(pcbnew.VECTOR2I(hauteur_min, hauteur_min))
    b.Add(g)
    for pad in g.Pads():
        if pad.GetNetname():
            pad.SetNet(reseau(pad.GetNetname()))
nb_pistes = 0
for t in blk.GetTracks():
    # Duplicate() puis Cast() : « PCB_TRACK(t) » ne copie pas, il crée une piste vide dont t serait le parent
    # (constaté le 25/10/2026 : toutes les pistes du bloc perdues).
    u = t.Duplicate().Cast()
    poser(u)
    u.SetLocked(True)
    b.Add(u)
    u.SetNet(reseau(t.GetNetname()))
    nb_pistes += 1
nb_zones = 0
for z in blk.Zones():
    y = pcbnew.ZONE(z)
    poser(y)
    b.Add(y)
    if z.GetNetname():
        y.SetNet(reseau(z.GetNetname()))
    nb_zones += 1

# ---------- 3. la mention de la source et de la licence
face = pcbnew.B_SilkS if a.mention_face == 'B' else pcbnew.F_SilkS
mx, my = (float(v) for v in a.mention_position.split(',')) if a.mention_position else (cx, cy)
texte = pcbnew.PCB_TEXT(b)
texte.SetText(a.mention)
texte.SetLayer(face)
texte.SetTextSize(pcbnew.VECTOR2I(MM(1.0), MM(1.0)))
texte.SetTextThickness(MM(0.15))
texte.SetPosition(pcbnew.VECTOR2I(MM(mx), MM(my)))
if face == pcbnew.B_SilkS:
    texte.SetMirrored(True)
b.Add(texte)
pcbnew.SaveBoard(a.sortie, b)

print(f"Enlevé : {', '.join(retires)} ; {len(enlevees)} pistes et vias dans la zone ; {bouts} bouts de piste devenus inutiles")
print(f"Posé : bloc {fiche['nom']} ({fiche.get('licence', 'licence ?')}), centre ({cx}, {cy}), rotation {a.rotation:g}° ; "
      f"{len(reperes)} composants ({', '.join(f'{k} → {v}' for k, v in reperes.items())}) ; {nb_pistes} pistes et vias "
      f"verrouillées ; {nb_zones} zones")
print(f"Mention sur la sérigraphie ({'dessous' if a.mention_face == 'B' else 'dessus'}) : « {a.mention} »")
