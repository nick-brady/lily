import { Link } from 'react-router-dom';

// Shared shell for the privacy / terms pages: wordmark header, readable
// measure, consistent heading + body styles.
export default function LegalLayout({ title, updated, children }) {
  return (
    <div className="min-h-screen bg-white dark:bg-gray-950">
      <nav className="flex items-center justify-between px-6 py-5 max-w-3xl mx-auto">
        <Link
          to="/"
          className="text-3xl text-primary-600 dark:text-primary-400"
          style={{ fontFamily: "'Great Vibes', cursive" }}
        >
          Arrival Story
        </Link>
        <Link
          to="/login"
          className="text-sm text-gray-500 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
        >
          Log in
        </Link>
      </nav>

      <main className="max-w-3xl mx-auto px-6 pb-24 pt-6">
        <h1 className="text-3xl font-semibold text-gray-900 dark:text-white mb-1">{title}</h1>
        <p className="text-sm text-gray-400 dark:text-gray-500 mb-10">Last updated: {updated}</p>
        <div className="space-y-8">{children}</div>
      </main>

      <footer className="text-center py-8 text-gray-400 text-sm border-t border-gray-100 dark:border-gray-800 space-x-4">
        <Link to="/privacy" className="hover:text-primary-600 dark:hover:text-primary-400">Privacy Policy</Link>
        <Link to="/terms" className="hover:text-primary-600 dark:hover:text-primary-400">Terms of Service</Link>
      </footer>
    </div>
  );
}

export function LegalSection({ heading, children }) {
  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-3">{heading}</h2>
      <div className="space-y-3 text-[15px] leading-relaxed text-gray-600 dark:text-gray-300">
        {children}
      </div>
    </section>
  );
}
