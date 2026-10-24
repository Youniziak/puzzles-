"""Modèles 3D des composants d'une carte KiCad, posés comme sur la carte (les mêmes que la maquette à toucher).
Repère commun au boîtier et au banc de test : origine au coin bas-gauche du contour de la carte, axe y vers le haut,
z = 0 sur le dessus de la carte, en millimètres."""
import os
import cadquery as cq
import pcbnew
from shapely.geometry import box


class Carte3D:
    def __init__(self, carte, chemin_pcb):
        self.carte = carte
        self.board = pcbnew.LoadBoard(chemin_pcb)
        bb = self.board.GetBoardEdgesBoundingBox()
        self.X0, self.Y0 = pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetY())
        self.W, self.H = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
        self.EP = pcbnew.ToMM(self.board.GetDesignSettings().GetBoardThickness())
        r = carte.rayon
        self.contour = box(r, r, self.W - r, self.H - r).buffer(r, 32) if r > 0 else box(0, 0, self.W, self.H)
        self._modeles = {}
        self.formes, self.boites = {}, {}           # repère → forme CadQuery, boîte englobante
        self.sans_3d, self.dessous = [], []
        self.emprise_dessus, self.emprise_dessous = [], []   # rectangles (shapely) : ce qui occupe chaque face
        self.trous = []                              # trous de fixation : (repère, (x, y), diamètre du trou, relié à la masse)
        O, AZ = cq.Vector(0, 0, 0), cq.Vector(0, 0, 1)
        for fp in self.board.GetFootprints():
            ref = fp.GetReference()
            if 'mountinghole' in str(fp.GetFPID().GetLibItemName()).lower():
                pad = next(iter(fp.Pads()))
                self.trous.append((ref, self.xy(fp.GetPosition()), pcbnew.ToMM(pad.GetDrillSize().x),
                                   pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and bool(pad.GetNetname())))
                continue
            if fp.IsFlipped():
                self.dessous.append(ref)
                self.emprise_dessous.append(self.rect(fp.GetBoundingBox(False)))
                continue
            self.emprise_dessus.append(self.rect(fp.GetBoundingBox(False)))
            for p in fp.Pads():
                if p.GetDrillSize().x > 0:                     # patte ou trou traversant : dépasse sous la carte
                    self.emprise_dessous.append(self.rect(p.GetBoundingBox()))
            m = next(iter(fp.Models()), None)
            f = self._modele(m.m_Filename) if m else None
            if f is None:
                self.sans_3d.append(ref)
                continue
            f = f.rotate(O, AZ, m.m_Rotation.z).translate(cq.Vector(m.m_Offset.x, m.m_Offset.y, m.m_Offset.z))
            x, y = self.xy(fp.GetPosition())
            f = f.rotate(O, AZ, fp.GetOrientationDegrees()).translate(cq.Vector(x, y, 0))
            self.formes[ref], self.boites[ref] = f, f.BoundingBox()
            q = self.boites[ref]
            self.emprise_dessus.append(box(q.xmin, q.ymin, q.xmax, q.ymax))

    def xy(self, v):
        """Point KiCad (nm, y vers le bas) → repère de la carte (mm, y vers le haut)."""
        return pcbnew.ToMM(v.x) - self.X0, self.Y0 + self.H - pcbnew.ToMM(v.y)

    def rect(self, b):
        (ax, ay), (bx, by) = self.xy(b.GetOrigin()), self.xy(b.GetEnd())
        return box(min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))

    def _modele(self, chemin):
        nom = os.path.splitext(os.path.basename(chemin))[0]
        if nom not in self._modeles:
            step = os.path.join(self.carte.empreintes, self.carte.nom_bib + '.3dshapes', nom + '.step')
            self._modeles[nom] = cq.importers.importStep(step).val() if os.path.exists(step) else None
        return self._modeles[nom]

    @property
    def pattes(self):
        """De combien les pattes dépassent sous la carte (mm)."""
        return max([0] + [-q.zmin - self.EP for q in self.boites.values()])

    @property
    def plus_haut(self):
        ref = max(self.boites, key=lambda r: self.boites[r].zmax)
        return ref, self.boites[ref].zmax
