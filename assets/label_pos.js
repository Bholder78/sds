/* Overlay coordinates (percent of sticker image) for the secondary label template.
   Single source of truth used by index.html (print) and fill.html (on-screen).
   Calibrated pixel-measured against assets/secondary_sticker.png (2026-07-08). */
window.LABEL_POS = {
  NAME: { left: 22, top: 6.2, width: 33 },
  DATE: { left: 67.5, top: 6.2, width: 28 },
  SIG:  { DANGER: [90.8, 11.5], WARNING: [90.8, 15.2] },
  NF:   { H: [67, 38.5], F: [74.6, 32], R: [83, 38.5], S: [74.6, 45] },
  HM:   { H: [91.1, 56.9], F: [91.2, 63.1], R: [91.3, 69.5], P: [91.3, 75.9] },
  INFO: { left: 4.5, top: 58, width: 47, height: 17 },
  PPE: [["Safety Glasses",7.4,82.9],["Splash Goggles",7.4,86.6],["Face Shield",7.4,90.2],["Other",7.4,93.8],
        ["Dust Respirator",39.6,82.9],["Vapor Respirator",39.6,86.6],["Gloves",39.6,90.2],
        ["Apron",70.6,82.9],["Full Body Suit",70.6,86.6],["Boots",70.6,90.2]],
  PIC: { GHS09:[33.5,19], GHS04:[19,27.3], GHS05:[46,27.8], GHS01:[13.8,34.8], GHS02:[33.2,36.8],
         GHS03:[52,35.8], GHS06:[22.2,43], GHS07:[40.8,43], GHS08:[33.8,49.8] }
};
