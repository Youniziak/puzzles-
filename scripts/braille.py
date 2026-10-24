"""Braille par liblouis : la bibliothèque libre de référence (LGPL), celle des lecteurs d'écran (NVDA, Orca…).
Table par défaut : « fr-bfu-comp6.utb », le braille français ; les chiffres y sont en notation Antoine (signe de nombre
point 6, puis le chiffre), les majuscules ont leur signe. Une autre table se choisit dans les réglages.
Pas de table recopiée à la main dans la chaîne : liblouis est installé avec le paquet python3-louis."""
import louis

TABLE = 'fr-bfu-comp6.utb'


def cellules(texte, table=TABLE):
    """Texte → liste de cellules, chacune donnée par ses points (1 à 6). Une espace donne une cellule vide."""
    uni = louis.translateString(['unicode.dis', table], texte)
    return [[k + 1 for k in range(6) if (ord(c) - 0x2800) >> k & 1] for c in uni]


def taille(texte, br, table=TABLE):
    """Largeur et hauteur (mm) d'un texte braille, avec les dimensions de maquette.json (« braille »)."""
    n = len(cellules(texte, table))
    return (n - 1) * br['pas_cellule_mm'] + br['ecart_points_mm'] + br['point_diametre_mm'], 2 * br['ecart_points_mm'] + br['point_diametre_mm']


def points(texte, x0, y0, br, table=TABLE):
    """Centres des points ; (x0, y0) = point 1 de la première cellule, y vers le haut. Points 1-2-3 à gauche, 4-5-6 à droite."""
    pts = []
    for i, cel in enumerate(cellules(texte, table)):
        for d in cel:
            col, lig = (0, d - 1) if d <= 3 else (1, d - 4)
            pts.append((x0 + i * br['pas_cellule_mm'] + col * br['ecart_points_mm'], y0 - lig * br['ecart_points_mm']))
    return pts
