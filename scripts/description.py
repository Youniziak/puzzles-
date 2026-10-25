"""Lecture de la description d'une carte. C'est le seul endroit où la chaîne apprend ce qu'il y a sur la carte.

Une carte est un fichier JSON (dossier cartes/) : son contour, ses règles de fabrication, et la liste des blocs
posés, chacun avec sa position et sa rotation (0, 90, 180 ou 270 degrés).
Un bloc est un dossier de la bibliothèque (bibliotheque/blocs/NOM/) :
  - bloc.json : description, réseaux d'interface (ceux qui sortent du bloc), composants non posés (pastilles de sortie),
    zones sans cuivre (antenne…) et la liste de connexions du bloc, avec les courants ;
  - easygerber/ : l'export d'EasyGerber (design.json, BOM.csv, Gerber).

Noms sur la carte :
  - un réseau d'interface, ou la masse, garde son nom : c'est ce qui relie les blocs entre eux ;
  - un réseau interne garde son nom, sauf s'il existe ailleurs sur la carte : il est alors préfixé par le bloc (« B/XTAL_A ») ;
  - un repère de composant (R1…) qui existe dans deux blocs reçoit le numéro du bloc (« R1_2 »).
Un bloc posé peut renommer ses réseaux (« renommer »), par exemple pour poser deux fois le même ampli.
Trous de fixation (facultatif, « trous_fixation ») : diamètre du trou et du cuivre, reliés ou non à la masse, et
leurs positions, ou « auto » : les places libres (hors blocs, zones sans cuivre et couloirs entre deux blocs) les plus
proches des coins."""
import json, math, os, sys
from collections import Counter

def largeur_pour_courant(i_a, echauffement=10, epaisseur_um=35):
    """Largeur de cuivre (mm) pour un courant : IPC-2221, couche externe."""
    aire_mil2 = (i_a / (0.048 * echauffement ** 0.44)) ** (1 / 0.725)
    return aire_mil2 / (epaisseur_um / 25.4) * 0.0254

def champs_piece(p):
    """Champs d'un composant, les mêmes sur l'empreinte (assembler.py) et sur le symbole (schema.py) : la parité de KiCad les
    compare. Tirés de la pièce elle-même (export EasyGerber), et non de la bibliothèque : une empreinte partagée par plusieurs
    pièces (un 0603) portait la référence LCSC de la première pièce téléchargée (constaté le 24/10/2026 sur 18 composants)."""
    return [('LCSC Part', p.get('lcscPartNumber') or ''), ('MPN', p.get('mpn') or ''),
            ('Manufacturer', p.get('manufacturer') or ''), ('Datasheet', p.get('datasheet') or '')]


ROTATIONS = {0: lambda x, y: (x, y), 90: lambda x, y: (-y, x), 180: lambda x, y: (-x, -y), 270: lambda x, y: (y, -x)}


class BlocPose:
    """Un bloc de la bibliothèque, posé sur la carte. Coordonnées en mm, axe y vers le haut (comme EasyGerber)."""

    def __init__(self, carte, numero, entree, dossier_bibliotheque):
        self.numero = numero
        self.nom = entree['bloc']
        self.id = entree.get('id', self.nom)
        self.dossier = os.path.join(dossier_bibliotheque, 'blocs', self.nom)
        self.bloc = json.load(open(os.path.join(self.dossier, 'bloc.json'), encoding='utf-8'))
        self.easygerber = os.path.join(self.dossier, 'easygerber')
        self.design = json.load(open(os.path.join(self.easygerber, 'design.json'), encoding='utf-8'))
        self.rotation = int(entree.get('rotation', 0)) % 360
        if self.rotation not in ROTATIONS:
            raise ValueError(f"bloc {self.id} : rotation {self.rotation}° impossible (0, 90, 180 ou 270)")
        self.renommer = entree.get('renommer', {})
        w, h = self.design['board']['width'], self.design['board']['height']
        coins = [ROTATIONS[self.rotation](x, y) for x, y in ((0, 0), (w, 0), (0, h), (w, h))]
        self._min = (min(c[0] for c in coins), min(c[1] for c in coins))
        self.position = tuple(entree['position'])
        self.taille = (max(c[0] for c in coins) - self._min[0], max(c[1] for c in coins) - self._min[1])
        self.interface = {self.renommer.get(n, n) for n in self.bloc.get('interface', [])}
        self.courants_locaux = {c['net']: c['requiredCurrentA'] for c in self.bloc['intent']['connections'] if c.get('requiredCurrentA')}
        self.valeurs_locales = {p[0]: p[2] for p in self.bloc['intent']['parts']}

    def point(self, x, y):
        """Point du bloc (coordonnées EasyGerber du bloc) → point de la carte."""
        rx, ry = ROTATIONS[self.rotation](x, y)
        return rx - self._min[0] + self.position[0], ry - self._min[1] + self.position[1]

    def angle(self, a):
        return (a + self.rotation) % 360

    def rect(self, r):
        """Rectangle [x0, y0, x1, y1] du bloc → rectangle de la carte."""
        (ax, ay), (bx, by) = self.point(r[0], r[1]), self.point(r[2], r[3])
        return min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)

    def pastille(self, partie, q):
        """Centre d'une pastille EasyGerber (dans son composant) → point de la carte."""
        a = math.radians(partie['rotation'])
        x = partie['x'] + q['x'] * math.cos(a) - q['y'] * math.sin(a)
        y = partie['y'] + q['x'] * math.sin(a) + q['y'] * math.cos(a)
        return self.point(x, y)


class Carte:
    def __init__(self, chemin, regles=None):
        """regles : nom d'un autre fichier de règles (autre fabricant) ; par défaut, celui de la carte."""
        self.fichier = os.path.abspath(chemin)
        d = json.load(open(self.fichier, encoding='utf-8'))
        self.donnees = d
        self.nom = d['nom']
        self.bibliotheque = os.path.normpath(os.path.join(os.path.dirname(self.fichier), d.get('bibliotheque', '../bibliotheque')))
        self.nom_regles = regles or d['regles']
        self.regles = json.load(open(os.path.join(self.bibliotheque, 'regles', self.nom_regles + '.json'), encoding='utf-8'))
        c = d['contour']
        self.largeur, self.hauteur, self.rayon = c['largeur'], c['hauteur'], c.get('rayon_coins', 0.0)
        self.masse = d.get('masse', 'GND')
        self.empreintes = os.path.join(self.bibliotheque, 'empreintes')
        self.correspondance = json.load(open(os.path.join(self.empreintes, 'correspondance.json'), encoding='utf-8'))
        noms_bib = [f[:-len('.pretty')] for f in os.listdir(self.empreintes) if f.endswith('.pretty')]
        if not noms_bib:  # pas dans le dépôt : les conditions d'EasyEDA interdisent de la republier
            sys.exit("La bibliothèque des composants (empreintes, symboles et modèles 3D de LCSC) n'est pas encore là. "
                     "La télécharger d'abord : python3 outils/telecharger_bibliotheque.py")
        self.nom_bib = noms_bib[0]
        self.blocs = [BlocPose(self, i + 1, e, self.bibliotheque) for i, e in enumerate(d['blocs'])]
        self._noms()
        self._verifier_place()
        self._trous = None

    # --- noms des réseaux et des composants sur la carte
    def _noms(self):
        interface_partout = set().union(*(b.interface for b in self.blocs)) | {self.masse}
        internes = Counter()
        for b in self.blocs:
            locaux = {b.renommer.get(q.get('netName'), q.get('netName')) for p in b.design['parts'] for q in p['pads'] if q.get('netName')}
            locaux |= {b.renommer.get(t['net'], t['net']) for t in b.design['traces']}
            for n in locaux - b.interface - {self.masse}:
                internes[n] += 1
        self._a_prefixer = {n for n, k in internes.items() if k > 1 or n in interface_partout}
        reperes = Counter(p['id'] for b in self.blocs for p in b.design['parts'])
        self._reperes_doubles = {r for r, k in reperes.items() if k > 1}

    def reseau(self, b, local):
        """Nom sur la carte d'un réseau du bloc b ; None pour une broche non reliée."""
        if not local:
            return None
        n = b.renommer.get(local, local)
        if n in b.interface or n == self.masse or n not in self._a_prefixer:
            return n
        return f'{b.id}/{n}'

    def repere(self, b, local):
        return f'{local}_{b.numero}' if local in self._reperes_doubles else local

    # --- grandeurs utiles aux étapes
    @property
    def courants(self):
        """Courant demandé par réseau de la carte (le plus grand, si plusieurs blocs le donnent)."""
        out = {}
        for b in self.blocs:
            for n, i_a in b.courants_locaux.items():
                nom = self.reseau(b, n)
                out[nom] = max(out.get(nom, 0), i_a)
        return out

    def largeur_mini(self, i_a):
        a = self.regles['alimentations']
        return largeur_pour_courant(i_a, a['echauffement_C'], a['epaisseur_cuivre_um'])

    def largeur_classe(self, i_a):
        """Largeur donnée à Freerouting pour un réseau d'alimentation : mini × marge, arrondie au 0,05 mm supérieur."""
        a = self.regles['alimentations']
        w = self.largeur_mini(i_a) * a['marge_largeur']
        return max(self.regles['classe_par_defaut']['track_width'], math.ceil(w / 0.05 - 1e-9) * 0.05)

    @property
    def zones_sans_cuivre(self):
        return [(f"{b.id} : {z['raison']}", b.rect(z['rect'])) for b in self.blocs for z in b.bloc.get('sans_cuivre', [])]

    # --- trous de fixation
    TROU_DEFAUT = {'diametre_trou_mm': 3.2, 'diametre_cuivre_mm': 6.0, 'garde_mm': 0.5, 'masse': True,
                   'nombre': 4, 'ecart_min_mm': 15.0, 'positions': 'auto'}

    @property
    def trou(self):
        """Réglages des trous de fixation (ceux de la carte, complétés par les valeurs par défaut) ; None s'il n'y en a pas."""
        t = self.donnees.get('trous_fixation')
        return dict(self.TROU_DEFAUT, **t) if t else None

    @property
    def trous_fixation(self):
        """Centres des trous de fixation, en mm (axe y vers le haut, comme EasyGerber)."""
        if self._trous is None:
            self._trous = self._chercher_trous() if self.trou else []
        return self._trous

    def _chercher_trous(self):
        from shapely.geometry import Point, box
        from shapely.ops import unary_union
        t = self.trou
        r = t['diametre_cuivre_mm'] / 2 + t['garde_mm']
        bord = self.regles['kicad']['min_copper_edge_clearance'] + 0.2
        R = self.rayon
        contour = box(R, R, self.largeur - R, self.hauteur - R).buffer(R, 32) if R > 0 else box(0, 0, self.largeur, self.hauteur)
        occupe = [box(b.position[0], b.position[1], b.position[0] + b.taille[0], b.position[1] + b.taille[1]) for b in self.blocs]
        occupe += [box(*rect) for _, rect in self.zones_sans_cuivre]
        # couloirs entre deux blocs : les liaisons entre blocs y passent (constaté le 23/10/2026 : un trou entre
        # l'alimentation et l'ampli a empêché Freerouting de relier le 5 V)
        cadres = [(b.position[0], b.position[1], b.position[0] + b.taille[0], b.position[1] + b.taille[1]) for b in self.blocs]
        for i, (a0, b0, a1, b1) in enumerate(cadres):
            for (c0, d0, c1, d1) in cadres[i + 1:]:
                if min(b1, d1) > max(b0, d0):                      # face à face horizontalement
                    occupe.append(box(min(a1, c1), max(b0, d0), max(a0, c0), min(b1, d1)))
                if min(a1, c1) > max(a0, c0):                      # face à face verticalement
                    occupe.append(box(max(a0, c0), min(b1, d1), min(a1, c1), max(b0, d0)))
        libre = contour.buffer(-(t['diametre_cuivre_mm'] / 2 + bord)).difference(unary_union(occupe).buffer(r))
        if t['positions'] != 'auto':
            for x, y in t['positions']:
                if not libre.buffer(1e-6).contains(Point(x, y)):
                    raise ValueError(f"trou de fixation en ({x}, {y}) : pas libre (bloc, zone sans cuivre ou bord trop près)")
            return [tuple(p) for p in t['positions']]
        pas = 0.5
        grille = [(i * pas, j * pas) for i in range(int(self.largeur / pas) + 1) for j in range(int(self.hauteur / pas) + 1)]
        grille = [p for p in grille if libre.contains(Point(p))]
        choisis = []
        for cx, cy in ((0, 0), (self.largeur, 0), (0, self.hauteur), (self.largeur, self.hauteur)):
            for p in sorted(grille, key=lambda p: (math.hypot(p[0] - cx, p[1] - cy), p)):
                if all(math.hypot(p[0] - q[0], p[1] - q[1]) >= t['ecart_min_mm'] for q in choisis):
                    choisis.append(p)
                    break
            if len(choisis) == t['nombre']:
                break
        return choisis

    def _verifier_place(self):
        """Chaque bloc doit tenir dans la carte, sans chevaucher un autre bloc."""
        cadres = []
        for b in self.blocs:
            x0, y0 = b.position
            x1, y1 = x0 + b.taille[0], y0 + b.taille[1]
            if x0 < -0.01 or y0 < -0.01 or x1 > self.largeur + 0.01 or y1 > self.hauteur + 0.01:
                raise ValueError(f"bloc {b.id} hors de la carte : ({x0:.1f}, {y0:.1f}) → ({x1:.1f}, {y1:.1f}), carte {self.largeur} × {self.hauteur}")
            for autre, (a0, b0, a1, b1) in cadres:
                if x0 < a1 - 0.01 and a0 < x1 - 0.01 and y0 < b1 - 0.01 and b0 < y1 - 0.01:
                    raise ValueError(f"les blocs {autre} et {b.id} se chevauchent")
            cadres.append((b.id, (x0, y0, x1, y1)))
