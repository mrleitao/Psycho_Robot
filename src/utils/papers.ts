// Helpers for the paper pages. Every page takes its numbers from the printed paper; these helpers only
// reformat them or derive a quantity the paper's own numbers imply (named in the page's note).
import { minus, noZero } from './fmt';

// Signed number with a true minus sign and no leading zero: .26, −.15, 1.25.
export const sg = (n: number, digits = 2) => minus(noZero(n.toFixed(digits)));
// Number with a true minus sign, keeping the leading zero: 0.26, −0.15.
export const nm = (n: number, digits = 2) => minus(n.toFixed(digits));

// Approximate 95% interval for a between-groups Cohen's d from the total sample size, assuming equal groups.
// Standard error = sqrt(4 / N + d^2 / (2 N)).
export function dInterval(d: number, n: number): [number, number] {
  const se = Math.sqrt(4 / n + (d * d) / (2 * n));
  return [d - 1.96 * se, d + 1.96 * se];
}

// Percent change in a count for a given step, from a log-scale coefficient and its standard error.
export function pctPer(b: number, se: number, step: number): { v: number; lo: number; hi: number } {
  const p = (x: number) => (Math.exp(x * step) - 1) * 100;
  return { v: p(b), lo: p(b - 1.96 * se), hi: p(b + 1.96 * se) };
}

// 95% interval from an estimate and its standard error.
export const ci = (b: number, se: number): [number, number] => [b - 1.96 * se, b + 1.96 * se];

export const consistency = (rows: { paper: string; ok: boolean }[], paper: string) => {
  const r = rows.filter((x) => x.paper === paper);
  return { n: r.length, bad: r.filter((x) => !x.ok).length };
};
