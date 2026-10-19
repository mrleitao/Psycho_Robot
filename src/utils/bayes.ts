// Words for Bayes factors: "11 times more likely" reads more easily than "BF = 11".
const group = (n: number) => n.toLocaleString('en-US');

// How many times more likely, in words. Use for a Bayes factor of 1 or more.
export function times(b: number): string {
  if (b < 1.2) return 'about equally likely';
  if (b < 10) return `${b.toFixed(1).replace(/\.0$/, '')} times more likely`;
  if (b < 1000) return `${group(Math.round(b))} times more likely`;
  if (b < 1e6) return `${group(Math.round(b / 100) * 100)} times more likely`;
  if (b < 1e9) return `over ${group(Math.floor(b / 1e6))} million times more likely`;
  return 'over a billion times more likely';
}

// The number alone, for tight spaces like chart labels: 11×, 2.4×, 3,000×, 10⁶×.
export function timesShort(b: number): string {
  if (b >= 1e4) return `10${[...String(Math.floor(Math.log10(b)))].map((c) => '⁰¹²³⁴⁵⁶⁷⁸⁹'[Number(c)]).join('')}×`;
  if (b >= 100) return `${group(Math.round(b))}×`;
  if (b >= 10) return `${Math.round(b)}×`;
  return `${b.toFixed(1)}×`;
}

// Describe a row in a sentence. bf10 is the evidence for a difference.
export function sentence(bf10: number, what: string, sizeLabel = 'medium'): string {
  return bf10 >= 1
    ? `The data are ${times(bf10)} under a ${sizeLabel} ${what} than under no difference.`
    : `The data are ${times(1 / bf10)} under no difference than under a ${sizeLabel} ${what}.`;
}
