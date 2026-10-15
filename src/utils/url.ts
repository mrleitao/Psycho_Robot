// Prefix internal links with the site's base path (needed on GitHub Pages project sites).
const base = import.meta.env.BASE_URL.replace(/\/$/, '');

export const href = (path: string) => `${base}${path.startsWith('/') ? path : `/${path}`}`;
export const basePath = base;
