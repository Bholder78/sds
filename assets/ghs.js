/* GHS pictograms — official UN artwork (public domain), files in assets/ghs/.
   Shared by index.html and guide.html. */
(function(){
  var META = {
    GHS01: ["Exploding bomb", "Explosive"],
    GHS02: ["Flame", "Flammable"],
    GHS03: ["Flame over circle", "Oxidizer"],
    GHS04: ["Gas cylinder", "Compressed gas"],
    GHS05: ["Corrosion", "Corrosive"],
    GHS06: ["Skull and crossbones", "Acute toxic"],
    GHS07: ["Exclamation mark", "Irritant / harmful"],
    GHS08: ["Health hazard", "Health hazard"],
    GHS09: ["Environment", "Environmental"]
  };
  window.GHS = {};
  Object.keys(META).forEach(function(c){
    window.GHS[c] = {
      name: META[c][0],
      cls: META[c][1],
      svg: '<img src="assets/ghs/' + c + '.svg" alt="' + META[c][0] + '">'
    };
  });
  window.GHS_ORDER = ["GHS01","GHS02","GHS03","GHS04","GHS05","GHS06","GHS07","GHS08","GHS09"];
})();
