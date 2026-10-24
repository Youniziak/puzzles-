// Boîtier d'essai de « RADIONÉO carte radio v4 », écrit par la chaîne puzzle (boitier.py). Ne pas modifier à la main :
// changer bibliotheque/regles/boitier.json ou « boitier » dans bloc.json, puis relancer.
// Outil : YAPP_Box 3.3.8 (licence MIT, https://github.com/mrWheel/YAPP_Box).
include </tmp/claude-0/-home-claude/a74a14cb-1787-5557-95b8-25def8410e6c/scratchpad/recherche-hackaday/yapp-src/YAPP_Box/YAPPgenerator_v3.scad>

printBaseShell = true; printLidShell = true; printSwitchExtenders = true; printDisplayClips = false;
shiftLid = 10; showSideBySide = true; onLidGap = 0;
pcbLength = 80.050; pcbWidth = 73.050; pcbThickness = 1.600;
standoffHeight = 3.000; standoffDiameter = 5.0; standoffPinDiameter = 2.400; standoffHoleSlack = 0.4;
pcb = [["Main", pcbLength, pcbWidth, 0, 0, pcbThickness, standoffHeight, standoffDiameter, standoffPinDiameter, standoffHoleSlack]];
paddingFront = 1.0; paddingBack = 1.0; paddingRight = 1.0; paddingLeft = 1.0;
wallThickness = 2.0; basePlaneThickness = 1.6; lidPlaneThickness = 1.6;
baseWallHeight = 6.600; lidWallHeight = 11.250;
ridgeHeight = 4.0; ridgeSlack = 0.3; ridgeGap = 0.5; roundRadius = 2.0; boxType = 0;
printerLayerHeight = 0.2; renderQuality = 6; previewQuality = 5;
pcbStands = [
  [76.525, 58.525, yappBoth, yappPin],
  [18.525, 69.525, yappBoth, yappPin],
  [66.025, 69.525, yappBoth, yappPin],
  [3.525, 69.025, yappBoth, yappPin],
  [3.000, 3.000, yappBoth, yappHole, yappNoFillet],
  [77.000, 3.000, yappBoth, yappHole, yappNoFillet]
];
connectors = [];
cutoutsBase = [];
cutoutsLid = [
  [37.525, 51.530, 0, 0, 1.5, yappCircle, 0, 0, yappCoordPCB, yappCenter]   // D1 LED
];
cutoutsFront = [
  [49.225, 6.500, 0, 0, 5.750, yappCircle, 0, 0, yappCoordPCB, yappCenter],   // J2 FM
  [38.025, 2.500, 8.000, 4.000, 1.0, yappRoundedRect, 0, 0, yappCoordPCB, yappCenter]   // J3 AM
];
cutoutsBack = [
  [30.025, 2.500, 8.000, 4.000, 1.0, yappRoundedRect, 0, 0, yappCoordPCB, yappCenter]   // J6 MOLETTE
];
cutoutsLeft = [
  [15.025, 0.001, 13.400, 7.600, 1.0, yappRoundedRect, 0, 0, yappCoordPCB, yappCenter],   // J1 USB
  [57.695, 2.500, 8.000, 4.000, 1.0, yappRoundedRect, 0, 0, yappCoordPCB, yappCenter],   // J4 HP G
  [48.695, 2.500, 8.000, 4.000, 1.0, yappRoundedRect, 0, 0, yappCoordPCB, yappCenter]   // J5 HP D
];
cutoutsRight = [];
snapJoins = [
  [42.500, 6, yappLeft, yappCenter],
  [43.000, 6, yappRight, yappCenter]
];
lightTubes = [];
pushButtons = [
  [5.025, 30.026, 0, 0, 4.5, 2.5, 1.500, 0.3, 3.5, undef, yappCircle],   // SW1 RESET
  [35.525, 57.526, 8.0, 8.0, 0, 2.5, 1.500, 0.3, 3.5, undef, yappRectangle]   // SW2 BOOT
];
labelsPlane = [
  [26.825, 33.026, 0, 0.8, yappLid, "DejaVu Sans:style=Bold", 5.0, "RESET", 0, yappTextLeftToRight, yappTextHAlignCenter, yappTextVAlignCenter, 1.0],
  [38.525, 71.206, 0, 0.8, yappLid, "DejaVu Sans:style=Bold", 5.0, "BOOT", 0, yappTextLeftToRight, yappTextHAlignCenter, yappTextVAlignCenter, 1.0],
  [40.525, 48.530, 0, 0.8, yappLid, "DejaVu Sans:style=Bold", 5.0, "LED", 0, yappTextLeftToRight, yappTextHAlignCenter, yappTextVAlignCenter, 1.0],
  [18.025, 7.000, 0, 0.8, yappLid, "DejaVu Sans:style=Bold", 5.0, "USB", 0, yappTextLeftToRight, yappTextHAlignCenter, yappTextVAlignCenter, 1.0],
  [76.427, 52.225, 0, 0.8, yappLid, "DejaVu Sans:style=Bold", 5.0, "FM", 0, yappTextLeftToRight, yappTextHAlignCenter, yappTextVAlignCenter, 1.0],
  [21.889, 23.025, 0, 0.8, yappLid, "DejaVu Sans:style=Bold", 5.0, "MOLETTE", 0, yappTextLeftToRight, yappTextHAlignCenter, yappTextVAlignCenter, 1.0],
  [75.817, 41.025, 0, 0.8, yappLid, "DejaVu Sans:style=Bold", 5.0, "AM", 0, yappTextLeftToRight, yappTextHAlignCenter, yappTextVAlignCenter, 1.0],
  [60.695, 7.000, 0, 0.8, yappLid, "DejaVu Sans:style=Bold", 5.0, "HP G", 0, yappTextLeftToRight, yappTextHAlignCenter, yappTextVAlignCenter, 1.0],
  [51.695, 14.000, 0, 0.8, yappLid, "DejaVu Sans:style=Bold", 5.0, "HP D", 0, yappTextLeftToRight, yappTextHAlignCenter, yappTextVAlignCenter, 1.0]
];
YAPPgenerate();
