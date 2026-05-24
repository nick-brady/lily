import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../api/client';

const DEFAULT_BIRTH_SLUG = import.meta.env.VITE_DEFAULT_BIRTH_SLUG || 'lily-wren';

export default function AuthVerifyPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { acceptToken } = useAuth();
  const [error, setError] = useState('');

  useEffect(() => {
    const token = params.get('token');
    if (!token) {
      setError('No token provided.');
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const result = await api.verifyChallenge({ token });
        if (cancelled) return;
        await acceptToken(result.access_token);
        navigate(`/b/${DEFAULT_BIRTH_SLUG}/manage`, { replace: true });
      } catch (err) {
        if (!cancelled) setError(err.message || 'This link is invalid or expired.');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [params, acceptToken, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900 px-4">
      <div className="w-full max-w-sm bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6 text-center">
        {error ? (
          <>
            <h1 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
              Sign-in failed
            </h1>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">{error}</p>
            <button
              onClick={() => navigate('/login', { replace: true })}
              className="px-4 py-2 rounded-lg bg-primary-600 text-white font-medium hover:bg-primary-700"
            >
              Try again
            </button>
          </>
        ) : (
          <p className="text-gray-500 dark:text-gray-400">Signing you in…</p>
        )}
      </div>
    </div>
  );
}
