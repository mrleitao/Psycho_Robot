// Number formatting and table-row helpers shared by the Study 3, 4 and 5 pages.
export const f1 = (n: number | null | undefined) => (n == null ? '' : n.toFixed(1));
export const f2 = (n: number | null | undefined) => (n == null ? '' : n.toFixed(2));
export const f3 = (n: number) => n.toFixed(3);
export const noZero = (s: string) => s.replace(/^(-?)0\./, '$1.');
export const minus = (s: string) => s.replace(/^-/, '−').replace(/\[-/g, '[−').replace(/, -/g, ', −').replace(/\(-/g, '(−');
export const pv = (p: number) => (p < 0.001 ? '< .001' : noZero(p.toFixed(3)));
export const pEq = (p: number) => (p < 0.001 ? 'p < .001' : `p = ${noZero(p.toFixed(3))}`);
export const r3 = (n: number) => minus(noZero(n.toFixed(3)));

export const descCols = [
  { key: 'label', label: 'Group' },
  { key: 'n', label: 'n', num: true, hint: 'People with an answer' },
  { key: 'mean', label: 'Mean', num: true },
  { key: 'sd', label: 'SD', num: true, hint: 'Standard deviation' },
  { key: 'se', label: 'SE', num: true, hint: 'Standard error of the mean' },
  { key: 'ci', label: '95% CI', num: true },
  { key: 'median', label: 'Median', num: true },
  { key: 'min', label: 'Min', num: true },
  { key: 'max', label: 'Max', num: true },
];
export const descRow = (r: any, label: string) => ({
  label, n: r.n, mean: minus(f2(r.mean)), sd: f2(r.sd), se: f2(r.se), ci: minus(`[${f2(r.lo)}, ${f2(r.hi)}]`),
  median: minus(f2(r.median)), min: minus(f2(r.min)), max: minus(f2(r.max)),
});

// Two separate groups (Welch t test, d from the pooled SD).
export const betweenCols = (firstName = 'First', secondName = 'Second') => [
  { key: 'text', label: 'Comparison', wrap: true, minw: '13rem' },
  { key: 'means', label: `${firstName}, ${secondName}: mean (SD)`, num: true, wrap: true, minw: '9.5rem' },
  { key: 'diff', label: 'Difference [95% CI]', num: true },
  { key: 't', label: 't (df)', num: true },
  { key: 'p', label: 'p', num: true },
  { key: 'd', label: 'd [95% CI]', num: true, hint: 'Cohen’s d: the mean difference over the pooled standard deviation' },
];
export const betweenRow = (t: any, text = t.label) => ({
  text,
  means: minus(`${f2(t.meanA)} (${f2(t.sdA)}), ${f2(t.meanB)} (${f2(t.sdB)})`),
  diff: minus(`${f2(t.diff)} [${f2(t.lo)}, ${f2(t.hi)}]`),
  t: minus(`${f2(t.t)} (${t.df})`),
  p: pv(t.p),
  d: minus(`${f2(t.d)} [${f2(t.dLo)}, ${f2(t.dHi)}]`),
});

// The same people rated both recommenders (paired t test, dz).
export const pairedCols = [
  { key: 'text', label: 'Comparison', wrap: true, minw: '13rem' },
  { key: 'n', label: 'n', num: true },
  { key: 'means', label: 'First, second: mean (SD)', num: true, wrap: true, minw: '9.5rem' },
  { key: 'diff', label: 'Difference [95% CI]', num: true },
  { key: 't', label: 't (df)', num: true },
  { key: 'p', label: 'p', num: true },
  { key: 'pb', label: 'Bonferroni p', num: true, hint: 'p multiplied by the number of comparisons in the family, capped at 1' },
  { key: 'd', label: 'dz [95% CI]', num: true, hint: 'Cohen’s d for paired data: the mean difference over the SD of the differences' },
  { key: 'dir', label: 'Higher / same / lower', num: true, hint: 'How many people rated the first recommender higher, the same, or lower than the second' },
];
export const pairedRow = (t: any, text = t.label) => ({
  text, n: t.n,
  means: minus(`${f2(t.meanA)} (${f2(t.sdA)}), ${f2(t.meanB)} (${f2(t.sdB)})`),
  diff: minus(`${f2(t.diff)} [${f2(t.lo)}, ${f2(t.hi)}]`),
  t: minus(`${f2(t.t)} (${t.df})`),
  p: pv(t.p),
  pb: t.pBonferroni == null ? '' : pv(t.pBonferroni),
  d: minus(`${f2(t.d)} [${f2(t.dLo)}, ${f2(t.dHi)}]`),
  dir: `${t.higher} / ${t.same} / ${t.lower}`,
});

export const olsCols = [
  { key: 'term', label: 'Predictor', wrap: true, minw: '14rem' },
  { key: 'b', label: 'b', num: true },
  { key: 'ci', label: '95% CI', num: true },
  { key: 'se', label: 'SE', num: true },
  { key: 't', label: 't', num: true },
  { key: 'p', label: 'p', num: true },
];
export const olsRows = (m: any) =>
  m.terms.map((t: any) => {
    const h = 1.96 * t.se;
    return { term: t.term, b: minus(f3(t.b)), ci: minus(`[${f3(t.b - h)}, ${f3(t.b + h)}]`), se: f3(t.se), t: minus(f2(t.t)), p: pv(t.p) };
  });
export const olsFit = (m: any) => `${m.n} people. R² ${noZero(m.r2.toFixed(3))}, adjusted R² ${noZero(m.r2adj.toFixed(3))}, ${m.df} residual degrees of freedom. Intervals are b ± 1.96 SE.`;

export const lmmCols = [
  { key: 'term', label: 'Predictor', wrap: true, minw: '14rem' },
  { key: 'b', label: 'b [95% CI]', num: true },
  { key: 'beta', label: 'Standardized β', num: true, hint: 'b times the SD of the predictor over the SD of the outcome. Not given for interactions.' },
  { key: 'z', label: 'z', num: true },
  { key: 'p', label: 'p', num: true },
];
export const lmmRows = (m: any) =>
  m.terms.map((t: any) => ({
    term: t.term, b: minus(`${f3(t.b)} [${f3(t.lo)}, ${f3(t.hi)}]`), beta: t.beta == null ? '' : minus(f2(t.beta)), z: minus(f2(t.z)), p: pv(t.p),
  }));
export const lmmFit = (m: any) =>
  `${m.n.toLocaleString('en-US')} ratings from ${m.people} people. Person variance ${f2(m.varPerson)}, residual ${f2(m.varResidual)}. Share of variance between people (ICC) ${noZero(f2(m.icc))}. R² ${noZero(f2(m.r2m))} from the predictors alone, ${noZero(f2(m.r2c))} with the person effects.`;

// Coefficient dots for a model: the raw b with its interval, intercept left out.
export const coefFig = (m: any) =>
  m.terms.filter((t: any) => t.term !== 'Intercept').map((t: any) => {
    const lo = t.lo ?? t.b - 1.96 * t.se, hi = t.hi ?? t.b + 1.96 * t.se;
    return { label: t.term, v: t.b, lo, hi, tip: `b = ${t.b.toFixed(2)} (95% CI ${lo.toFixed(2)} to ${hi.toFixed(2)})` };
  });
export const coefDomain = (rows: any[], pad = 0.1): [number, number] => {
  const a = Math.min(0, ...rows.map((x) => x.lo)), b = Math.max(0, ...rows.map((x) => x.hi));
  return [Math.floor((a - pad) * 5) / 5, Math.ceil((b + pad) * 5) / 5];
};
export const dRefs = [{ v: 0.2, label: 'small' }, { v: 0.41, label: 'medium' }, { v: 0.63, label: 'large' }];

export const sampleRows = (sample: any) =>
  sample.variables.flatMap((v: any) => v.rows.map((r: any) => ({ label: `${v.variable}: ${r.group}`, n: r.n, pct: `${r.pct.toFixed(1)}%` })));
export const sampleFig = (sample: any) =>
  sample.variables.flatMap((v: any) => [{ head: v.variable }, ...v.rows.map((r: any) => ({ label: `${r.group} (n = ${r.n})`, v: r.pct, tip: `${r.n} of ${sample.n} people (${r.pct}%)` }))]);
export const missingNote = (sample: any) => sample.variables.filter((v: any) => v.missing).map((v: any) => `${v.variable.toLowerCase()} (${v.missing})`).join(', ');
export const REPO = 'https://github.com/mrleitao/Psycho_Robot';
