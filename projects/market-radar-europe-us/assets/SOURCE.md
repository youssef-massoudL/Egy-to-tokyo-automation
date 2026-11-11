# Sources: market-radar-europe-us

- **Map:** Natural Earth admin-0 countries, 1:50m (public domain), via the `world-atlas` 2.0.2 npm package (topojson, read with
  `topojson-client` 3.1.0), projected with `d3-geo` 3.1.1 Mercator (3000 px per radian, origin lon -128 / lat 72, extent to lon 42 / lat 18)
  into `map-data.js`. Generated 2026-11-03. Highlight ids: de, fr, es, it, gb, us. Same projection convention as
  `market-radar-cairo-tokyo`, with the origin stored in the file (`MAP.LON0`, `MAP.LAT0`).
- **Index levels and daily changes:** see the header of `../data.js` (sources and cross-checks per index, per day).
- **Look:** as `market-radar-daily` (brand tokens; lavender = up, red = loss, grey = closed).
- **Sound:** music + SFX of the source video `shaaban made reels/kanz-market-performance-cairo-tokyo.mp4`, muxed on after rendering
  (event times unchanged).
