import { renderToString } from 'react-dom/server';
import { StaticRouter } from 'react-router-dom/server';
import { AppRoutes } from './App';
import { AuthProvider } from './contexts/AuthContext';
import { PageTracking } from './hooks/usePageTracking';
import { PUBLIC_ROUTES, metaFor } from './seo/routeMeta';

// The build-time entry. `scripts/prerender.mjs` calls render() once per
// public route and writes the result into a copy of index.html, so a crawler
// (or anyone with JavaScript off) gets the page's words on the first byte.
// Nothing here runs on the server at request time: this is a build step.
//
// The tree has the same shape as the browser's (PageTracking renders nothing
// and its effects never run here, but React's useId is derived from tree
// position, so the siblings must match for the wordmark's mask id to
// hydrate cleanly). No StrictMode: that is a development aid for the browser.
export function render(url) {
  const html = renderToString(
    <AuthProvider>
      <StaticRouter location={url}>
        <PageTracking />
        <AppRoutes />
      </StaticRouter>
    </AuthProvider>,
  );
  return { html, meta: metaFor(url) };
}

export { PUBLIC_ROUTES };
