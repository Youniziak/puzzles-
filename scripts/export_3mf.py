"""Écrit un fichier 3MF en couleurs : une seule pièce, faite de plusieurs parties, chacune avec sa couleur et son nom.
Le 3MF est le format des imprimantes à plusieurs couleurs (plusieurs bobines de fil). Chaque partie porte le nom
de sa couleur, pour que la personne qui imprime puisse lui donner le bon fil si son logiciel ne lit pas la couleur.
Usage : ecrire_3mf(chemin, [(nom, '#RRGGBB', forme CadQuery), ...], tolerance)"""
import zipfile
from xml.sax.saxutils import quoteattr

TYPES = ('<?xml version="1.0" encoding="UTF-8"?>\n'
         '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
         '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
RELS = ('<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')


def ecrire_3mf(chemin, parties, tolerance=0.05, tolerance_angle=0.3, nom_piece='maquette'):
    lignes = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<model unit="millimeter" xml:lang="fr-FR" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">',
              '<resources>', '<basematerials id="1">']
    for nom, rgb, _ in parties:
        lignes.append(f'<base name={quoteattr(nom)} displaycolor="{rgb.upper()}FF"/>')
    lignes.append('</basematerials>')
    ids, triangles_total = [], 0
    for k, (nom, rgb, forme) in enumerate(parties):
        sommets, triangles = forme.tessellate(tolerance, tolerance_angle)
        if not triangles:
            continue
        oid = k + 2
        ids.append(oid)
        triangles_total += len(triangles)
        lignes.append(f'<object id="{oid}" name={quoteattr(nom)} type="model" pid="1" pindex="{k}"><mesh><vertices>')
        lignes.extend(f'<vertex x="{v.x:.4f}" y="{v.y:.4f}" z="{v.z:.4f}"/>' for v in sommets)
        lignes.append('</vertices><triangles>')
        lignes.extend(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in triangles)
        lignes.append('</triangles></mesh></object>')
    piece = max(ids) + 1
    lignes.append(f'<object id="{piece}" name={quoteattr(nom_piece)} type="model"><components>')
    lignes.extend(f'<component objectid="{i}"/>' for i in ids)
    lignes += ['</components></object>', '</resources>', f'<build><item objectid="{piece}"/></build>', '</model>']
    with zipfile.ZipFile(chemin, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', TYPES)
        z.writestr('_rels/.rels', RELS)
        z.writestr('3D/3dmodel.model', '\n'.join(lignes))
    return len(ids), triangles_total
