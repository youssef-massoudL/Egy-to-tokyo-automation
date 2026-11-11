/* Market Radar edition: Cairo -> Tokyo, published at the EGX close. The scene is ../_radar/scene.js; the day's numbers are in data.js. */
window.RADAR = {
  kick: "أداء الأسواق",
  title: "من القاهرة لطوكيو",
  track: 488,
  stops: [
    { k: "egx30", pin: "cairo", name: "EGX30", code: "", where: "مصر", rank: "مصر" },
    { k: "tasi", pin: "riyadh", name: "تاسي", code: "TASI", where: "السعودية", rank: "السعودية" },
    { k: "dfmgi", pin: "dubai", name: "سوق دبي", code: "DFMGI", where: "الإمارات", rank: "الإمارات" },
    { k: "fadgi", pin: "abudhabi", name: "فوتسي أبوظبي", code: "FADGI", where: "الإمارات", rank: "الإمارات" },
    { k: "nifty", pin: "mumbai", name: "نيفتي 50", code: "NIFTY 50", where: "الهند", rank: "الهند" },
    { k: "hsi", pin: "hongkong", name: "هانج سنج", code: "HSI", where: "هونج كونج", rank: "هونج كونج" },
    { k: "kospi", pin: "seoul", name: "كوسبي 200", code: "KOSPI 200", where: "كوريا الجنوبية", rank: "كوريا الجنوبية" },
    { k: "n225", pin: "tokyo", name: "نيكاي 225", code: "N225", where: "اليابان", rank: "اليابان" },
  ],
  country: { eg: ["egx30"], sa: ["tasi"], ae: ["dfmgi", "fadgi"], in: ["nifty"], kr: ["kospi"], jp: ["n225"] },
  pins: { cairo: [31.23, 30.04, 2.40], riyadh: [46.72, 24.71, 3.95], dubai: [55.27, 25.2, 5.15], abudhabi: [54.37, 24.45, 5.48],
    mumbai: [72.88, 19.08, 7.55], hongkong: [114.17, 22.32, 9.2], seoul: [126.98, 37.57, 10.75], tokyo: [139.69, 35.68, 11.95] },
  lit: [["eg", 2.35], ["sa", 3.85], ["ae", 5.05], ["in", 7.35], ["kr", 10.65], ["jp", 11.9]],
  cards: [{ at: 2.53, out: 3.95, dy: 210 }, { at: 4.03, out: 5.1, dy: 200 }, { at: 5.2, out: 7.0, dy: -175, dx: -250 }, { at: 5.53, out: 7.0, dy: 170 },
    { at: 7.63, out: 8.75, dy: 190 }, { at: 9.27, out: 10.3, dy: -200 }, { at: 10.8, out: 13.45, dy: 160, dx: -90 }, { at: 12.0, out: 13.45, dy: -150, dx: 40 }],
  ev: [2.77, 4.20, 5.16, 5.80, 7.72, 9.40, 10.93, 12.12],
  start: { lon: 31, lat: 27.5, s: 1.25 },
  route(move, tl, cam, SY) {
    move(2.2, 31, 27.5, 1.42, 1.1, SY, "sine.inOut");  // Egypt: slow push
    move(3.65, 44.5, 24, 0.98);                          // Saudi Arabia
    move(5.0, 54.6, 24.8, 3.0);                          // UAE
    move(7.2, 78, 21.5, 0.68);                           // India
    move(8.9, 113.5, 24, 2.8);                           // Hong Kong
    move(10.4, 127, 36, 2.5);                            // Korea
    move(11.75, 133.5, 35.6, 1.42);                      // Japan (Korea still in view)
  },
  overview: { lon: 84, lat: 29, s: [0.14, 0.152, 0.17] },
};
