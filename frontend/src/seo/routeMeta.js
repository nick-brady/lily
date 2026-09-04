// What each page says about itself to a crawler, a link unfurler, and the
// browser tab. One map, read two ways: `scripts/prerender.mjs` writes it
// into the <head> of the pre-rendered public pages at build time, and
// `usePageMeta` applies it in the browser on every client-side navigation.
//
// Only four pages are public. Everything else is a family's private page or
// the tooling around it and is marked noindex — as a header from nginx and
// as a meta tag from here, so a leaked link never lands in an index.

export const SITE = 'https://arrivalstory.com';
export const SITE_NAME = 'Arrival Story';
export const OG_IMAGE = `${SITE}/og-image.jpg`;

const TAGLINE = 'The birth story your whole family lives together';

const ORGANIZATION = {
  '@type': 'Organization',
  name: SITE_NAME,
  url: SITE,
  logo: `${SITE}/apple-touch-icon.png`,
};

export const PUBLIC_ROUTES = {
  '/': {
    title: `${SITE_NAME}: ${TAGLINE.toLowerCase()}`,
    description:
      'Set up your baby’s page in two minutes and share one link. Family follows the labour and birth live, and everything stays free to keep.',
    jsonLd: {
      '@context': 'https://schema.org',
      '@graph': [
        ORGANIZATION,
        {
          '@type': 'WebSite',
          name: SITE_NAME,
          url: SITE,
          description: TAGLINE,
          publisher: { '@type': 'Organization', name: SITE_NAME, url: SITE },
        },
      ],
    },
  },
  '/pricing': {
    title: `Pricing · ${SITE_NAME}`,
    description:
      'Everything live is free: updates, photos, the contraction timer, unlimited family. You only pay for keepsakes and for keeping the page up after the first year.',
  },
  '/privacy': {
    title: `Privacy Policy · ${SITE_NAME}`,
    description:
      'What Arrival Story collects, why, and what it never does with a family’s photos, updates and contacts.',
  },
  '/terms': {
    title: `Terms of Service · ${SITE_NAME}`,
    description: 'The terms for using Arrival Story, in plain language.',
  },
};

// Prefixes, matched longest-first. A family's page and the tooling around it.
export const PRIVATE_PREFIXES = ['/account', '/setup', '/login', '/invite', '/b'];

// Tab titles for the private routes — never indexed, but a screen reader
// reads the title first, and five pages called "Arrival Story" are one page.
const PRIVATE_TITLES = {
  '/account': `Your account · ${SITE_NAME}`,
  '/setup': `Set up your baby’s page · ${SITE_NAME}`,
  '/login': `Sign in · ${SITE_NAME}`,
  '/invite': `Your invitation · ${SITE_NAME}`,
};

const DEFAULT_TITLE = SITE_NAME;

export function metaFor(pathname) {
  const path = pathname.replace(/\/+$/, '') || '/';
  const entry = PUBLIC_ROUTES[path];
  if (entry) {
    return {
      path,
      title: entry.title,
      description: entry.description,
      canonical: path === '/' ? `${SITE}/` : `${SITE}${path}`,
      robots: 'index, follow',
      jsonLd: entry.jsonLd || null,
      image: OG_IMAGE,
    };
  }
  const prefix = PRIVATE_PREFIXES.find((p) => path === p || path.startsWith(`${p}/`));
  if (prefix) {
    return { path, title: PRIVATE_TITLES[prefix] || DEFAULT_TITLE, description: null, canonical: null, robots: 'noindex, nofollow', jsonLd: null, image: null };
  }
  return null;
}
