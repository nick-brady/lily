import { describe, it, expect } from 'vitest';
import { PUBLIC_ROUTES, PRIVATE_PREFIXES, metaFor, SITE } from './routeMeta';

describe('routeMeta', () => {
  it('every public page has a title and description a result page can show whole', () => {
    for (const [path, entry] of Object.entries(PUBLIC_ROUTES)) {
      expect(entry.title.length, `${path} title`).toBeLessThanOrEqual(65);
      expect(entry.description.length, `${path} description`).toBeLessThanOrEqual(160);
      expect(entry.description.length, `${path} description`).toBeGreaterThan(50);
    }
  });

  it('public pages are indexable with an absolute canonical', () => {
    expect(metaFor('/')).toMatchObject({ robots: 'index, follow', canonical: `${SITE}/` });
    expect(metaFor('/pricing')).toMatchObject({ canonical: `${SITE}/pricing` });
    expect(metaFor('/pricing/')).toMatchObject({ canonical: `${SITE}/pricing` });
  });

  it('a family page and the tooling around it are noindex', () => {
    for (const prefix of PRIVATE_PREFIXES) {
      expect(metaFor(prefix)?.robots, prefix).toBe('noindex, nofollow');
      expect(metaFor(`${prefix}/anything-here`)?.robots, prefix).toBe('noindex, nofollow');
    }
    expect(metaFor('/b/lily-wren').canonical).toBeNull();
  });

  it('a route it does not know is left alone', () => {
    expect(metaFor('/something-else')).toBeNull();
    // "/blog" must not be mistaken for a birth page under /b
    expect(metaFor('/blog')).toBeNull();
  });

  it('the home page carries an organisation and a website, nothing invented', () => {
    const graph = PUBLIC_ROUTES['/'].jsonLd['@graph'];
    const types = graph.map((n) => n['@type']);
    expect(types).toEqual(['Organization', 'WebSite']);
    expect(JSON.stringify(graph)).not.toMatch(/rating|review|price/i);
  });
});
