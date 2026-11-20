// Participant counts by study. "own" means I led or ran the data collection myself.
// Sources: Matthew's confirmations (dissertation recruited 3,000+ including pilots and excluded participants) and the study pages.
export interface Count { name: string; n: number; basis: string; own: boolean }
export const counts: Count[] = [
  { name: 'Dissertation, six studies', n: 3000, basis: 'recruited, including pilots and excluded participants', own: true },
  { name: 'Smartphone experiments, pooled analysis', n: 1778, basis: 'analyzed, eight experiments', own: false },
  { name: 'Generative AI at work, two experiments', n: 1299, basis: 'recruited', own: false },
  { name: 'Fans and favorite characters', n: 829, basis: 'completed', own: false },
  { name: 'COVID-19 social interactions week', n: 569, basis: 'completed', own: true },
  { name: 'Gaming motivations scale', n: 572, basis: 'recruited, two samples', own: false },
  { name: 'Master’s thesis, obedience to computers', n: 305, basis: 'recruited', own: true },
  { name: 'Risk creep, eight-week study', n: 304, basis: 'enrolled', own: false },
  { name: 'Virtual reality symptom questionnaire validation', n: 100, basis: 'participants', own: true },
  { name: 'Virtual reality buffet in a drug trial', n: 29, basis: 'completers in the analysis, 42 enrolled', own: false },
  { name: 'Phone use and sleep', n: 91, basis: 'students', own: false },
];
export const total = counts.reduce((a, c) => a + c.n, 0);
export const own = counts.filter((c) => c.own).reduce((a, c) => a + c.n, 0);
