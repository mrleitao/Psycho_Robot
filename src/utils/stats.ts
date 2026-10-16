// Small statistics routines used by the interactive charts. No libraries.
// Checked against scipy in analysis/check-stats.mjs.

export const lgamma = (x: number): number => {
  const c = [76.18009172947146, -86.50532032941677, 24.01409824083091, -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5];
  let y = x;
  let t = x + 5.5;
  t -= (x + 0.5) * Math.log(t);
  let s = 1.000000000190015;
  for (const k of c) s += k / ++y;
  return -t + Math.log((2.5066282746310005 * s) / x);
};

const betacf = (a: number, b: number, x: number) => {
  const tiny = 1e-30;
  let c = 1;
  let d = 1 - ((a + b) * x) / (a + 1);
  if (Math.abs(d) < tiny) d = tiny;
  d = 1 / d;
  let h = d;
  for (let m = 1; m <= 300; m++) {
    const m2 = 2 * m;
    let aa = (m * (b - m) * x) / ((a + m2 - 1) * (a + m2));
    d = 1 + aa * d;
    if (Math.abs(d) < tiny) d = tiny;
    c = 1 + aa / c;
    if (Math.abs(c) < tiny) c = tiny;
    d = 1 / d;
    h *= d * c;
    aa = (-(a + m) * (a + b + m) * x) / ((a + m2) * (a + m2 + 1));
    d = 1 + aa * d;
    if (Math.abs(d) < tiny) d = tiny;
    c = 1 + aa / c;
    if (Math.abs(c) < tiny) c = tiny;
    d = 1 / d;
    const del = d * c;
    h *= del;
    if (Math.abs(del - 1) < 1e-12) break;
  }
  return h;
};

/** Regularized incomplete beta function. */
export const ibeta = (x: number, a: number, b: number) => {
  if (x <= 0) return 0;
  if (x >= 1) return 1;
  const bt = Math.exp(lgamma(a + b) - lgamma(a) - lgamma(b) + a * Math.log(x) + b * Math.log(1 - x));
  return x < (a + 1) / (a + b + 2) ? (bt * betacf(a, b, x)) / a : 1 - (bt * betacf(b, a, 1 - x)) / b;
};

/** Two-sided p value for a t statistic. */
export const pTwoSided = (t: number, df: number) => ibeta(df / (df + t * t), df / 2, 0.5);

/** Critical t for a two-sided test at the given alpha (default: 95% interval). */
export const tCritical = (df: number, alpha = 0.05) => {
  let lo = 0;
  let hi = 80;
  for (let i = 0; i < 80; i++) {
    const mid = (lo + hi) / 2;
    if (pTwoSided(mid, df) > alpha) lo = mid;
    else hi = mid;
  }
  return (lo + hi) / 2;
};

/** Standard normal cumulative distribution. */
export const pnorm = (x: number) => {
  // Abramowitz and Stegun 26.2.17 is too coarse for tails, so use the complementary error function.
  const erfc = (z: number) => {
    const t = 1 / (1 + 0.5 * Math.abs(z));
    const r =
      t *
      Math.exp(
        -z * z - 1.26551223 +
          t * (1.00002368 + t * (0.37409196 + t * (0.09678418 + t * (-0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (-0.82215223 + t * 0.17087277))))))))
      );
    return z >= 0 ? r : 2 - r;
  };
  return 0.5 * erfc(-x / Math.SQRT2);
};
