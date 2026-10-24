"""Essai fraiseuse : enlève tout le routage d'une carte (pistes, vias, plans de cuivre), en gardant les composants et
leur placement. Freerouting refera alors tout le routage, avec les règles de la carte.
Avec une garde (mm), ajoute le long du bord une bande où ni piste ni via ne peuvent passer : Freerouting ne connaît pas
l'écart au bord demandé par les règles (constaté le 24/10/2026 : 5 pistes et vias à moins de 0,5 mm du bord).
Avec « une-face » : ni piste sur la face du dessous, ni via ; Freerouting doit tout faire sur le dessus (carte fraisée
sur une seule face, sans trou à souder à la main).
Usage : python3 vider_routage.py carte.kicad_pcb [garde_mm] [une-face]"""
import sys
import pcbnew

board = pcbnew.LoadBoard(sys.argv[1])
garde = float(sys.argv[2]) if len(sys.argv) > 2 else 0
pistes = list(board.GetTracks())
vias = sum(1 for t in pistes if t.GetClass() == 'PCB_VIA')
for t in pistes:
    board.Delete(t)
zones = [z for z in board.Zones() if not z.GetIsRuleArea()]
for z in zones:
    board.Delete(z)

if garde:
    bb = board.GetBoardEdgesBoundingBox()
    x0, y0, x1, y1 = bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()
    g = pcbnew.FromMM(garde)
    for (a, b, c, d) in ((x0, y0, x1, y0 + g), (x0, y1 - g, x1, y1), (x0, y0, x0 + g, y1), (x1 - g, y0, x1, y1)):
        ka = pcbnew.ZONE(board)
        ka.SetIsRuleArea(True); ka.SetDoNotAllowZoneFills(True); ka.SetDoNotAllowTracks(True); ka.SetDoNotAllowVias(True)
        ka.SetZoneName('garde au bord (fraiseuse)')
        ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.B_Cu); ka.SetLayerSet(ls)
        ol = ka.Outline(); ol.NewOutline()
        for x, y in ((a, b), (c, b), (c, d), (a, d)):
            ol.Append(x, y)
        board.Add(ka)

une_face = 'une-face' in sys.argv[3:]
if une_face:
    bb = board.GetBoardEdgesBoundingBox()
    ka = pcbnew.ZONE(board)
    ka.SetIsRuleArea(True); ka.SetDoNotAllowZoneFills(True); ka.SetDoNotAllowTracks(True); ka.SetDoNotAllowVias(True)
    ka.SetZoneName('une seule face (fraiseuse)')
    ls = pcbnew.LSET(); ls.AddLayer(pcbnew.B_Cu); ka.SetLayerSet(ls)
    ol = ka.Outline(); ol.NewOutline()
    for x, y in ((bb.GetLeft(), bb.GetTop()), (bb.GetRight(), bb.GetTop()), (bb.GetRight(), bb.GetBottom()), (bb.GetLeft(), bb.GetBottom())):
        ol.Append(x, y)
    board.Add(ka)

board.Save(sys.argv[1])
print(f"enlevé : {len(pistes) - vias} pistes, {vias} vias, {len(zones)} plans de cuivre ; gardé : {len(board.GetFootprints())} composants"
      + (f" ; garde au bord : {garde:g} mm" if garde else '') + (" ; une seule face" if une_face else ''))
