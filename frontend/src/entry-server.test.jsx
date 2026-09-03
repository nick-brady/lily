import { describe, it, expect } from 'vitest';
import { render, PUBLIC_ROUTES } from './entry-server';

// The regression test for the build-time pre-render: if anything in the
// public pages' import graph reaches for `window` during render again, or a
// page bails out to nothing, this fails here rather than at deploy.

function section(html, id) {
  // the hero is the first <section>; enough for the assertions below
  const start = html.indexOf('<section');
  const end = html.indexOf('</section>', start);
  return html.slice(start, end);
}

describe('render()', () => {
  it('renders every public route without touching the browser', () => {
    for (const route of Object.keys(PUBLIC_ROUTES)) {
      const { html, meta } = render(route);
      expect(html.length, route).toBeGreaterThan(2000);
      expect(meta.canonical, route).toMatch(/^https:\/\/arrivalstory\.com/);
      expect((html.match(/<h1/g) || []).length, `${route} has one h1`).toBe(1);
    }
  });

  it('the landing page carries its words, not just its video', () => {
    const { html } = render('/');
    expect(html).toContain('Arrival Story');
    expect(html).toContain('The birth story your whole family lives together');
    expect(html).toContain('How it works');
    expect(html).toContain('From bump to baby');
    expect(html).toContain('One place to update, not scattered threads.');
    expect(html).toContain('<main>');
    expect(html).toContain('<nav');
    expect(html).toContain('<footer');
  });

  it('the demo phones are empty until the browser fills them', () => {
    // Their timelines are built from Date.now() and the visitor's locale and
    // could never match between build machine and browser.
    const { html } = render('/');
    const hero = section(html, 'hero');
    expect(hero).not.toMatch(/\bago\b/);
    expect(hero).not.toContain('Contraction in progress');
    expect(html).not.toContain('lily-demo');
  });

  it('the legal and pricing pages carry their headings', () => {
    expect(render('/pricing').html).toContain('What&#x27;s free (and what isn&#x27;t)');
    expect(render('/privacy').html).toContain('Privacy Policy');
    expect(render('/terms').html).toContain('Terms of Service');
  });

  it('renders the hero as the poster, never the video, at build time', () => {
    const { html } = render('/');
    expect(html).not.toContain('<video');
    expect(html).toContain('hero-poster');
  });
});
