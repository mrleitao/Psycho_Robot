import { ibeta, lgamma, pnorm, tCritical } from './stats';

/** Cumulative distribution of the noncentral t (Lenth, 1989, Algorithm AS 243). */
export const nctCdf = (t: number, df: number, ncp: number): number => {
  let negdel = false;
  let tt = t;
  let del = ncp;
  if (t < 0) {
    negdel = true;
    tt = -t;
    del = -ncp;
  }
  const x = (tt * tt) / (tt * tt + df);
  let tnc = 0;
  if (x > 0) {
    const lambda = del * del;
    let p = 0.5 * Math.exp(-0.5 * lambda);
    let q = Math.sqrt(2 / Math.PI) * p * del;
    let s = 0.5 - p;
    if (s < 1e-7) s = -0.5 * Math.expm1(-0.5 * lambda);
    let a = 0.5;
    const b = 0.5 * df;
    const rxb = Math.pow(1 - x, b);
    const albeta = 0.5 * Math.log(Math.PI) + lgamma(b) - lgamma(0.5 + b);
    let xodd = ibeta(x, a, b);
    let godd = 2 * rxb * Math.exp(a * Math.log(x) - albeta);
    tnc = b * x;
    let xeven = tnc < Number.EPSILON ? tnc : 1 - rxb;
    let geven = tnc * rxb;
    tnc = p * xodd + q * xeven;
    for (let it = 1; it <= 1000; it++) {
      a += 1;
      xodd -= godd;
      xeven -= geven;
      godd *= (x * (a + b - 1)) / a;
      geven *= (x * (a + b - 0.5)) / (a + 0.5);
      p *= lambda / (2 * it);
      q *= lambda / (2 * it + 1);
      tnc += p * xodd + q * xeven;
      s -= p;
      if (s < -1e-10) break;
      if (s <= 0 && it > 1) break;
      const errbd = 2 * s * (xodd - godd);
      if (Math.abs(errbd) < 1e-12) break;
    }
  }
  tnc += pnorm(-del);
  tnc = Math.min(tnc, 1);
  return negdel ? 1 - tnc : tnc;
};

/** Power of a two-sided paired (or one-sample) t test: n pairs, effect size d, significance level alpha. */
export const powerPaired = (d: number, n: number, alpha = 0.05): number => {
  if (n < 3) return alpha;
  const df = n - 1;
  const tc = tCritical(df, alpha);
  const ncp = d * Math.sqrt(n);
  return Math.min(1, Math.max(0, 1 - nctCdf(tc, df, ncp) + nctCdf(-tc, df, ncp)));
};

/** Smallest number of pairs that reaches the target power, or null if more than maxN are needed. */
export const nNeeded = (d: number, alpha = 0.05, target = 0.8, maxN = 5000): number | null => {
  if (d <= 0) return null;
  let lo = 3;
  let hi = 8;
  while (powerPaired(d, hi, alpha) < target) {
    lo = hi;
    hi *= 2;
    if (hi > maxN) return powerPaired(d, maxN, alpha) < target ? null : bisectN(d, alpha, target, lo, maxN);
  }
  return bisectN(d, alpha, target, lo, hi);
};
const bisectN = (d: number, alpha: number, target: number, lo: number, hi: number) => {
  while (hi - lo > 1) {
    const mid = Math.floor((lo + hi) / 2);
    if (powerPaired(d, mid, alpha) < target) lo = mid;
    else hi = mid;
  }
  return hi;
};

/** Smallest effect size d that n pairs can detect with the target power. */
export const minDetectable = (n: number, alpha = 0.05, target = 0.8): number => {
  let lo = 0;
  let hi = 5;
  for (let i = 0; i < 40; i++) {
    const mid = (lo + hi) / 2;
    if (powerPaired(mid, n, alpha) < target) lo = mid;
    else hi = mid;
  }
  return (lo + hi) / 2;
};
