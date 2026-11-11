/* Market Radar edition: Europe -> New York, published at the US close. The scene is ../_radar/scene.js; the day's numbers are in data.js.
 * Europe = UK, Germany, France only (user, 3 Nov). The three US indices say what they are, on the card and in the ranking.
 * Cards land on the music's beat (hits every ~0.27 s). */
const WHAT = { dow: "30 شركة عملاقة", spx: "500 شركة كبرى", ndq: "تقوده التكنولوجيا" };
window.RADAR = {
  kick: "أسواق الغرب",
  title: "من أوروبا لنيويورك",
  track: 428,
  stops: [
    { k: "dax", pin: "frankfurt", name: "داكس", code: "DAX", where: "ألمانيا", rank: "ألمانيا" },
    { k: "cac", pin: "paris", name: "كاك 40", code: "CAC 40", where: "فرنسا", rank: "فرنسا" },
    { k: "ftse", pin: "london", name: "فوتسي 100", code: "FTSE 100", where: "بريطانيا", rank: "بريطانيا" },
    { k: "dow", pin: "newyork", name: "داو جونز", code: "DJIA", where: `<em>${WHAT.dow}</em>`, rank: WHAT.dow },
    { k: "spx", pin: "newyork", name: "إس آند بي 500", code: "S&amp;P 500", where: `<em>${WHAT.spx}</em>`, rank: WHAT.spx },
    { k: "ndq", pin: "newyork", name: "ناسداك", code: "NASDAQ", where: `<em>${WHAT.ndq}</em>`, rank: WHAT.ndq },
  ],
  country: { de: ["dax"], fr: ["cac"], gb: ["ftse"], us: ["dow", "spx", "ndq"] },
  pins: { frankfurt: [8.68, 50.11, 2.40], paris: [2.35, 48.86, 3.82], london: [-0.13, 51.51, 5.30], newyork: [-74.01, 40.71, 8.30] },
  lit: [["de", 2.35], ["fr", 3.78], ["gb", 5.25], ["us", 8.1]],
  // the three US cards stay up together (top to bottom: Dow, S&P, Nasdaq)
  cards: [{ at: 2.5, out: 3.85, dy: 210 }, { at: 3.91, out: 5.25, dy: 200 }, { at: 5.39, out: 6.95, dy: -190, dx: -60 },
    { at: 8.4, out: 13.45, dy: -335 }, { at: 9.81, out: 13.45, dy: -180 }, { at: 11.17, out: 13.45, dy: 190 }],
  ev: [2.77, 4.17, 5.65, 8.67, 10.17, 11.46],
  start: { lon: 10.4, lat: 51.1, s: 1.05 },
  route(move, tl, cam, SY) {
    move(2.2, 10.4, 51.1, 1.18, 1.1, SY, "sine.inOut");  // Germany: slow push
    move(3.6, 2.4, 46.6, 1.0);                             // France
    move(5.05, -2.6, 54.2, 1.0);                           // United Kingdom
    // across the Atlantic: rise while flying west, then come down on New York
    tl.to(cam, { lon: -74.0, lat: 40.7, duration: 1.05, ease: "power2.inOut" }, 6.9);
    tl.to(cam, { lz: Math.log(0.3), duration: 0.45, ease: "sine.inOut" }, 6.9);
    tl.to(cam, { lz: Math.log(1.5), duration: 0.7, ease: "power2.out" }, 7.35);
    move(9.5, -73.8, 40.8, 1.62, 1.1, SY, "sine.inOut");   // slow push while the S&P lands
    move(10.9, -74.0, 40.7, 1.5, 1.0, SY, "sine.inOut");   // ease back so the three sit together
  },
  overview: { lon: -33, lat: 46.5, s: [0.175, 0.188, 0.21] },
};
