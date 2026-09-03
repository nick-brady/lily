// Pre-render the public pages into dist/, after `vite build` has produced the
// SPA and `vite build --ssr` has produced a Node build of the same components
// in dist/.ssr. Runs as the last step of `npm run build`; see package.json.
//
//   dist/app.html              ←  the untouched SPA shell (empty #root)
//   dist/index.html            ←  /
//   dist/pricing/index.html    ←  /pricing      (and so on)
//
// nginx tries `$uri/index.html` before falling back to app.html, so these
// answer their URLs and every other route — a family's page, say — still
// gets the empty shell rather than the pre-rendered home page.
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { buildPage, outputPath } from './prerenderHtml.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const dist = resolve(here, '..', 'dist');
const ssrDir = resolve(dist, '.ssr');

// A page that rendered to nothing must fail the build, not ship. The
// smallest real page (terms) is well over this.
const MIN_BODY_BYTES = 2000;

const { render, PUBLIC_ROUTES } = await import(pathToFileURL(resolve(ssrDir, 'entry-server.js')).href);
const template = readFileSync(resolve(dist, 'index.html'), 'utf8');
// the shell has to survive under its own name before / overwrites index.html
writeFileSync(resolve(dist, 'app.html'), template);
console.log('shell        → app.html');

for (const route of Object.keys(PUBLIC_ROUTES)) {
  const { html, meta } = render(route);
  if (!meta) throw new Error(`${route}: no metadata`);
  if (html.length < MIN_BODY_BYTES) {
    throw new Error(`${route}: rendered only ${html.length} bytes — a component bailed out`);
  }
  const page = buildPage(template, { html, meta }, 'Arrival Story');
  const out = resolve(dist, outputPath(route));
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, page);
  console.log(`prerendered ${route.padEnd(9)} → ${outputPath(route)} (${(html.length / 1024).toFixed(1)} KB body)`);
}

rmSync(ssrDir, { recursive: true, force: true });
