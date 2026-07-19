import { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import HeroVideo from '../components/landing/HeroVideo';
import PhoneCarouselSection from '../components/landing/PhoneCarouselSection';

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

      {/* Hero — full-bleed video + synced phone UI (Lily-Hero-Video-Plan.md) */}
      <HeroVideo />

      {/* Phone demo carousel: silence the group chat, then keep the keepsake */}
      <PhoneCarouselSection />

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
