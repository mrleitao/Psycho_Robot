// Effect-size language for the whole site, after Funder and Ozer (2019), "Evaluating effect size in psychological research".
// Their benchmarks are correlations: r = .05 very small, .10 small, .20 medium, .30 large, .40 very large.
// A d is converted with r = d / sqrt(d^2 + 4), the conversion for two equal groups. For paired ratings this is a convention, not an exact identity.
export const FUNDER_OZER = [
  { r: 0.05, d: 0.1, label: 'very small' },
  { r: 0.1, d: 0.2, label: 'small' },
  { r: 0.2, d: 0.41, label: 'medium' },
  { r: 0.3, d: 0.63, label: 'large' },
  { r: 0.4, d: 0.87, label: 'very large' },
] as const;

export const dToR = (d: number) => d / Math.sqrt(d * d + 4);

// An effect is named after the nearest benchmark. Below half the "very small" benchmark it is called negligible.
export function effectLabel(d: number | null | undefined): string {
  if (d == null || !Number.isFinite(d)) return '';
  const r = Math.abs(dToR(d));
  if (r < 0.025) return 'negligible';
  let best: (typeof FUNDER_OZER)[number] = FUNDER_OZER[0];
  for (const b of FUNDER_OZER) if (Math.abs(b.r - r) < Math.abs(best.r - r)) best = b;
  return best.label;
}
