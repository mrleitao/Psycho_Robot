// Compare the browser statistics routines with scipy.
// Run: npx esbuild src/utils/power.ts --bundle --format=esm --outfile=/tmp/power.mjs && node analysis/check-stats.mjs /tmp/power.mjs  (then compare with the scipy values printed by analysis/check-stats.py)
const m = await import(process.argv[2]);
const cases = [[0.2, 100, 0.05], [0.5, 34, 0.05], [0.8, 15, 0.05], [0.41, 188, 0.01], [0.07, 609, 0.05], [0.19, 185, 0.05]];
for (const [d, n, a] of cases) console.log(JSON.stringify({ d, n, a, power: +m.powerPaired(d, n, a).toFixed(5) }));
console.log(JSON.stringify({ n_for_d05: m.nNeeded(0.5), n_for_d02: m.nNeeded(0.2), mde188: +m.minDetectable(188).toFixed(4), mde24: +m.minDetectable(24).toFixed(4) }));
