// The string surgery behind scripts/prerender.mjs, kept apart so it can be
// unit-tested without a build: take the SPA shell (dist/index.html) and one
// route's rendered body and metadata, and produce that route's page.

const ROOT_RE = /<div id="root"><\/div>/;
const TITLE_RE = /<title>[^<]*<\/title>/;
const HEAD_CLOSE = '</head>';

function esc(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

// Drop any tag from the template that we are about to write ourselves, so a
// page never carries two descriptions or two og:titles.
function stripManaged(template) {
  return template
    .replace(/[ \t]*<meta name="description"[^>]*>\n?/g, '')
    .replace(/[ \t]*<meta property="og:[^"]*"[^>]*>\n?/g, '')
    .replace(/[ \t]*<meta name="twitter:[^"]*"[^>]*>\n?/g, '')
    .replace(/[ \t]*<meta name="robots"[^>]*>\n?/g, '')
    .replace(/[ \t]*<link rel="canonical"[^>]*>\n?/g, '')
    .replace(/[ \t]*<script type="application\/ld\+json">[\s\S]*?<\/script>\n?/g, '');
}

export function headFor(meta, siteName) {
  const tags = [
    `<meta name="description" content="${esc(meta.description)}" />`,
    `<meta name="robots" content="${esc(meta.robots)}" />`,
    `<link rel="canonical" href="${esc(meta.canonical)}" />`,
    `<meta property="og:site_name" content="${esc(siteName)}" />`,
    `<meta property="og:type" content="website" />`,
    `<meta property="og:url" content="${esc(meta.canonical)}" />`,
    `<meta property="og:title" content="${esc(meta.title)}" />`,
    `<meta property="og:description" content="${esc(meta.description)}" />`,
    `<meta property="og:image" content="${esc(meta.image)}" />`,
    `<meta property="og:image:width" content="1200" />`,
    `<meta property="og:image:height" content="630" />`,
    `<meta name="twitter:card" content="summary_large_image" />`,
    `<meta name="twitter:title" content="${esc(meta.title)}" />`,
    `<meta name="twitter:description" content="${esc(meta.description)}" />`,
    `<meta name="twitter:image" content="${esc(meta.image)}" />`,
  ];
  if (meta.jsonLd) {
    // "</" inside JSON would end the script element early
    const json = JSON.stringify(meta.jsonLd).replace(/<\//g, '<\\/');
    tags.push(`<script type="application/ld+json">${json}</script>`);
  }
  return tags.map((t) => `    ${t}`).join('\n');
}

export function buildPage(template, { html, meta }, siteName) {
  if (!ROOT_RE.test(template)) throw new Error('template has no empty <div id="root">');
  if (!TITLE_RE.test(template)) throw new Error('template has no <title>');
  const head = headFor(meta, siteName);
  return stripManaged(template)
    .replace(TITLE_RE, `<title>${esc(meta.title)}</title>`)
    .replace(HEAD_CLOSE, `${head}\n  ${HEAD_CLOSE}`)
    .replace(ROOT_RE, `<div id="root">${html}</div>`);
}

// dist/pricing/index.html for "/pricing"; dist/index.html for "/".
export function outputPath(route) {
  return route === '/' ? 'index.html' : `${route.replace(/^\//, '')}/index.html`;
}
