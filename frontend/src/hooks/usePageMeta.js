import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { metaFor } from '../seo/routeMeta';

// Keeps the document head honest as the visitor moves through the SPA: the
// tab title, the description, the robots directive, the canonical link. The
// pre-rendered public pages arrive with all of this already in place; this
// keeps it right after a client-side navigation.
//
// A route the map doesn't know is left alone — the birth page sets its own
// title from the child's name.

function upsertMeta(name, content) {
  let el = document.head.querySelector(`meta[name="${name}"]`);
  if (content == null) {
    el?.remove();
    return;
  }
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute('name', name);
    document.head.appendChild(el);
  }
  el.setAttribute('content', content);
}

function upsertCanonical(href) {
  let el = document.head.querySelector('link[rel="canonical"]');
  if (!href) {
    el?.remove();
    return;
  }
  if (!el) {
    el = document.createElement('link');
    el.setAttribute('rel', 'canonical');
    document.head.appendChild(el);
  }
  el.setAttribute('href', href);
}

export function usePageMeta() {
  const { pathname } = useLocation();
  useEffect(() => {
    const meta = metaFor(pathname);
    if (!meta) return;
    document.title = meta.title;
    upsertMeta('description', meta.description);
    upsertMeta('robots', meta.robots);
    upsertCanonical(meta.canonical);
  }, [pathname]);
}

// Rendered inside the router; contributes nothing to the DOM.
export function PageMeta() {
  usePageMeta();
  return null;
}
