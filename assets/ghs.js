/* GHS pictogram SVGs — red diamond frame, black symbol. Shared by index.html, guide.html and printed labels. */
(function(){
  function dia(inner){
    return '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">' +
      '<path d="M50 4 96 50 50 96 4 50Z" fill="#fff" stroke="#d90000" stroke-width="7" stroke-linejoin="round"/>' +
      '<g fill="#111" stroke="none">' + inner + '</g></svg>';
  }
  window.GHS = {
    GHS01: { name: "Exploding bomb", cls: "Explosive", svg: dia(
      '<circle cx="50" cy="58" r="10"/>' +
      '<g stroke="#111" stroke-width="4" stroke-linecap="round" fill="none">' +
      '<path d="M50 44v-12M50 72v12M36 58H24M64 58h12M40 48l-8-8M60 48l8-8M40 68l-8 8M60 68l8 8"/></g>') },
    GHS02: { name: "Flame", cls: "Flammable", svg: dia(
      '<path d="M50 24c2 10-8 14-8 24 0 4 2 7 4 9-6-1-12-7-12-16-6 6-9 12-9 19 0 12 11 20 25 20s25-8 25-20c0-13-12-17-14-30-4 3-6 7-5 12-4-4-7-11-6-18z"/>') },
    GHS03: { name: "Flame over circle", cls: "Oxidizer", svg: dia(
      '<path d="M52 22c1 7-6 10-6 17 0 3 1 5 3 6-4-1-8-5-8-11-4 4-6 8-6 13 0 8 7 13 17 13s17-5 17-13c0-9-8-12-10-21-3 2-4 5-3 8-3-3-5-7-4-12z"/>' +
      '<path d="M30 68h40v6H30z"/>') },
    GHS04: { name: "Gas cylinder", cls: "Compressed gas", svg: dia(
      '<rect x="40" y="34" width="20" height="42" rx="9"/>' +
      '<rect x="45" y="26" width="10" height="8"/>' +
      '<rect x="52" y="22" width="10" height="5"/>') },
    GHS05: { name: "Corrosion", cls: "Corrosive", svg: dia(
      '<path d="M28 30h14l-6 10 8 8-4 4-10-10 3-5h-5z"/>' +
      '<path d="M58 30h14v6h-5l3 5-10 10-4-4 8-8-6-9z" transform="scale(-1,1) translate(-130,0)"/>' +
      '<rect x="24" y="64" width="22" height="6"/>' +
      '<path d="M62 52c4 6 7 10 7 14a7 7 0 0 1-14 0c0-4 3-8 7-14z"/>' +
      '<path d="M56 66h20l4 10H52z"/>') },
    GHS06: { name: "Skull and crossbones", cls: "Acute toxic", svg: dia(
      '<path d="M50 24c-11 0-19 8-19 17 0 6 3 10 7 13v7h24v-7c4-3 7-7 7-13 0-9-8-17-19-17z"/>' +
      '<circle cx="42" cy="42" r="4.5" fill="#fff"/><circle cx="58" cy="42" r="4.5" fill="#fff"/>' +
      '<path d="M47 52h6l-3 6z" fill="#fff"/>' +
      '<g stroke="#111" stroke-width="6" stroke-linecap="round"><path d="M30 66l40 12M70 66L30 78"/></g>') },
    GHS07: { name: "Exclamation mark", cls: "Irritant / harmful", svg: dia(
      '<path d="M44 24h12l-3 34h-6z"/><circle cx="50" cy="70" r="7"/>') },
    GHS08: { name: "Health hazard", cls: "Health hazard", svg: dia(
      '<circle cx="50" cy="27" r="8"/>' +
      '<path d="M38 38h24v22l-6 20h-4l3-20h-10l3 20h-4l-6-20z"/>' +
      '<g fill="#fff"><path d="M50 40l4 8 9 1-6 6 2 9-9-5-9 5 2-9-6-6 9-1z"/></g>') },
    GHS09: { name: "Environment", cls: "Environmental", svg: dia(
      '<path d="M30 30l6 10-4 2 7 11-5 2 9 13h-8v6h-6v-6h-8l9-13-5-2 7-11-4-2z" transform="translate(4,-4)"/>' +
      '<path d="M56 66c6-6 14-8 20-6-2 7-8 12-14 12-2 0-4-1-6-2l-6 5-3-3 6-5c-1-2-1-4 0-6 1 2 2 4 3 5z"/>') }
  };
  window.GHS_ORDER = ["GHS01","GHS02","GHS03","GHS04","GHS05","GHS06","GHS07","GHS08","GHS09"];
})();
