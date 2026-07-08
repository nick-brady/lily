import { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import WordmarkWriteOn from '../components/WordmarkWriteOn';

export default function LandingPage() {
  const { isAuthenticated, loading, me } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (loading) return;
    if (!isAuthenticated) return;
    const hasBirth = me?.families?.some((f) => f.births?.length > 0);
    navigate(hasBirth ? '/account' : '/setup', { replace: true });
  }, [isAuthenticated, loading, me, navigate]);

  if (loading) return null;

  return (
    <div className="min-h-screen bg-white dark:bg-gray-950">
      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-5 max-w-5xl mx-auto">
        <span
          className="text-3xl text-primary-600 dark:text-primary-400"
          style={{ fontFamily: "'Great Vibes', cursive" }}
        >
          Arrival Story
        </span>
        <Link
          to="/login"
          className="text-sm text-gray-500 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
        >
          Log in
        </Link>
      </nav>

      {/* Hero */}
      <section className="flex flex-col items-center text-center px-6 pt-12 pb-24 bg-gradient-to-b from-primary-50 to-white dark:from-gray-900 dark:to-gray-950">
        <h1 className="mb-6">
          <span className="sr-only">Arrival Story</span>
          <WordmarkWriteOn className="w-[290px] sm:w-[470px] max-w-full text-primary-600 dark:text-primary-400" />
        </h1>
        <div className="flex flex-col items-center motion-safe:animate-fade-up">
        <p className="text-2xl font-light text-gray-800 dark:text-gray-100 mb-3 max-w-md leading-snug">
          The birth story your whole family lives together
        </p>
        <p className="text-base text-gray-500 dark:text-gray-400 mb-10 max-w-sm">
          Set up in 2 minutes. Share a link. Everyone follows in real time.
        </p>
        <Link
          to="/setup"
          className="btn-primary text-base px-8 py-4"
        >
          Create your baby's page →
        </Link>

        {/* Mock preview card */}
        <div className="mt-16 w-full max-w-xs bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-5 border border-primary-100 dark:border-primary-900/40 text-left">
          <h2
            className="text-2xl text-primary-600 dark:text-primary-400 text-center mb-4"
            style={{ fontFamily: "'Great Vibes', cursive" }}
          >
            Welcoming Lily Wren
          </h2>
          <div className="flex items-center gap-3 mb-4 p-3 bg-primary-50 dark:bg-primary-900/20 rounded-xl">
            <div className="h-2.5 w-2.5 rounded-full bg-primary-500 animate-pulse-slow flex-shrink-0" />
            <div>
              <div className="text-xs text-gray-400 mb-0.5">Contraction in progress</div>
              <div className="text-xl font-mono font-semibold text-gray-800 dark:text-white tracking-tight">
                0:42
              </div>
            </div>
          </div>
          <div className="text-xs text-gray-400 mb-2 px-1">8 mins ago</div>
          <div className="text-sm text-gray-700 dark:text-gray-300 mb-3 px-1">
            Contractions are 5 minutes apart 💪
          </div>
          <div className="flex items-center gap-2">
            <span className="bg-rose-50 dark:bg-rose-900/20 text-rose-600 dark:text-rose-300 rounded-full px-3 py-1 text-xs font-medium">
              ❤️ 14
            </span>
            <span className="bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-300 rounded-full px-3 py-1 text-xs font-medium">
              🙏 8
            </span>
            <span className="bg-sky-50 dark:bg-sky-900/20 text-sky-600 dark:text-sky-300 rounded-full px-3 py-1 text-xs font-medium">
              🤩 5
            </span>
          </div>
        </div>
        </div>
      </section>

      {/* How it works */}
      <section className="max-w-4xl mx-auto px-6 py-20">
        <h2 className="text-3xl font-light text-center text-gray-800 dark:text-gray-100 mb-12">
          How it works
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="card text-center">
            <div className="text-4xl mb-4">🌸</div>
            <h3 className="font-semibold text-gray-800 dark:text-white mb-2">You set up</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 leading-relaxed">
              Type your baby's name and get a shareable page — in under 2 minutes.
            </p>
          </div>
          <div className="card text-center">
            <div className="text-4xl mb-4">📱</div>
            <h3 className="font-semibold text-gray-800 dark:text-white mb-2">Family follows</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 leading-relaxed">
              Share one link. Grandma, aunts, friends — everyone follows live from anywhere.
            </p>
          </div>
          <div className="card text-center">
            <div className="text-4xl mb-4">💝</div>
            <h3 className="font-semibold text-gray-800 dark:text-white mb-2">Together, forever</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 leading-relaxed">
              Reactions, live updates, every moment — a keepsake your family will return to for years.
            </p>
          </div>
        </div>
      </section>

      {/* Gentle unlock mention */}
      <section className="bg-primary-50 dark:bg-gray-900 py-16 px-6">
        <div className="max-w-xl mx-auto text-center">
          <p className="text-lg text-gray-700 dark:text-gray-300 font-light leading-relaxed">
            Family members can unlock the full experience — leaving comments to be there in every way that matters.
          </p>
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="py-20 px-6 text-center">
        <Link
          to="/setup"
          className="btn-primary text-base px-8 py-4"
        >
          Create your baby's page →
        </Link>
        <p className="mt-4 text-sm text-gray-400">Free to set up. No app to download.</p>
      </section>

      {/* Footer */}
      <footer className="text-center py-8 text-gray-400 text-sm border-t border-gray-100 dark:border-gray-800">
        <span
          className="text-primary-400 text-xl"
          style={{ fontFamily: "'Great Vibes', cursive" }}
        >
          Arrival Story
        </span>
        <p className="mt-2 text-xs text-gray-400">Made with love</p>
        <p className="mt-3 text-xs space-x-3">
          <Link to="/privacy" className="hover:text-primary-600 dark:hover:text-primary-400">Privacy Policy</Link>
          <Link to="/terms" className="hover:text-primary-600 dark:hover:text-primary-400">Terms of Service</Link>
        </p>
      </footer>
    </div>
  );
}
