import { describe, it, expect } from 'vitest';
import { buildPage, outputPath } from './prerenderHtml.mjs';

const template = `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>Arrival Story</title>
    <meta name="description" content="shell description" />
    <meta property="og:title" content="Arrival Story" />
    <meta name="twitter:card" content="summary" />
    <script type="module" src="/assets/index-abc.js"></script>
  </head>
  <body class="bg-gray-100">
    <div id="root"></div>
  </body>
</html>
`;

const meta = {
  title: 'Pricing · Arrival Story',
  description: 'What costs & what "doesn\'t"',
  canonical: 'https://arrivalstory.com/pricing',
  robots: 'index, follow',
  image: 'https://arrivalstory.com/og-image.jpg',
  jsonLd: { '@type': 'WebSite', note: '</script><script>alert(1)' },
};

describe('buildPage', () => {
  const page = buildPage(template, { html: '<main><h1>Pricing</h1></main>', meta }, 'Arrival Story');

  it('fills the root and keeps the rest of the shell', () => {
    expect(page).toContain('<div id="root"><main><h1>Pricing</h1></main></div>');
    expect(page).toContain('<script type="module" src="/assets/index-abc.js"></script>');
    expect(page).toContain('<body class="bg-gray-100">');
    expect(page).toContain('<html lang="en">');
  });

  it('writes exactly one of each managed tag', () => {
    expect(page.match(/<title>/g)).toHaveLength(1);
    expect(page).toContain('<title>Pricing · Arrival Story</title>');
    expect(page.match(/<meta name="description"/g)).toHaveLength(1);
    expect(page.match(/<meta property="og:title"/g)).toHaveLength(1);
    expect(page.match(/<meta name="twitter:card"/g)).toHaveLength(1);
    expect(page).toContain('content="summary_large_image"');
    expect(page).not.toContain('shell description');
    expect(page.match(/<link rel="canonical"/g)).toHaveLength(1);
    expect(page).toContain('href="https://arrivalstory.com/pricing"');
  });

  it('escapes attribute values and cannot be broken out of by json-ld', () => {
    expect(page).toContain('content="What costs &amp; what &quot;doesn\'t&quot;"');
    expect(page).toContain('<\\/script>');
    expect(page.match(/<\/script>/g)).toHaveLength(2); // the module script and the json-ld
  });

  it('refuses a template without an empty root', () => {
    expect(() => buildPage(template.replace('<div id="root"></div>', '<div id="root">x</div>'), { html: '', meta }, 'x')).toThrow(/root/);
  });
});

describe('outputPath', () => {
  it('maps routes to files nginx will find', () => {
    expect(outputPath('/')).toBe('index.html');
    expect(outputPath('/pricing')).toBe('pricing/index.html');
  });
});
