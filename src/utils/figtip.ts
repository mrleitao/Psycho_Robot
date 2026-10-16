// Hover and keyboard tooltips shared by the Study 1 figures.
// Each item carries data-label and data-lines (lines separated by "|") and sits inside a <figure data-fig>.
export function attachTips(fig: HTMLElement) {
  if (fig.dataset.tipped) return;
  fig.dataset.tipped = '1';
  const tip = fig.querySelector<HTMLElement>('.tip');
  if (!tip) return;
  const esc = (s: string) => s.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c] as string);
  const show = (el: Element) => {
    const d = (el as HTMLElement | SVGElement).dataset;
    const lines = (d.lines ?? '').split('|').filter(Boolean);
    tip.innerHTML = `<strong>${esc(d.label ?? '')}</strong>${lines.map((l) => `<span>${esc(l)}</span>`).join('')}`;
    tip.hidden = false;
    const fr = fig.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    const half = tip.offsetWidth / 2;
    tip.style.left = `${Math.max(half, Math.min(fr.width - half, r.left - fr.left + r.width / 2))}px`;
    tip.style.top = `${Math.max(tip.offsetHeight + 4, r.top - fr.top + 6)}px`;
  };
  const hide = () => (tip.hidden = true);
  fig.querySelectorAll('[data-tip]').forEach((el) => {
    el.addEventListener('pointerenter', () => show(el));
    el.addEventListener('pointerleave', hide);
    el.addEventListener('focus', () => show(el));
    el.addEventListener('blur', hide);
  });
}
