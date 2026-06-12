import { useState } from 'react';
import { api } from '../api/client';
import { THEMES, getTheme } from '../utils/themes';
import ThemeCard from './ThemeCard';

export default function ThemePickerSheet({ birth, onClose, onSaved }) {
  const [selected, setSelected] = useState(birth.theme || 'lily');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const displayName = birth.child_name || 'Baby';
  const accent = getTheme(selected).modes.light.accent;

  const save = async () => {
    if (selected === birth.theme) {
      onClose();
      return;
    }
    setSaving(true);
    setError('');
    try {
      await api.updateBirth(birth.id, { theme: selected });
      await onSaved?.();
      onClose();
    } catch (err) {
      setError(err.message || 'Could not save theme');
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-end sm:items-center justify-center"
      onClick={onClose}
    >
      <div
        className="animate-slide-up w-full sm:max-w-md bg-white dark:bg-gray-900
                   rounded-t-2xl sm:rounded-2xl shadow-xl p-5 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-center">
          <h2 className="text-base font-semibold text-gray-800 dark:text-white">
            Choose a look for {displayName}
          </h2>
        </div>

        <div className="grid grid-cols-3 gap-2.5">
          {Object.values(THEMES).map((t) => (
            <ThemeCard
              key={t.id}
              theme={t}
              displayName={displayName}
              selected={selected === t.id}
              onSelect={() => setSelected(t.id)}
            />
          ))}
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
            {error}
          </div>
        )}

        <div className="flex gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="flex-1 py-3 rounded-xl text-sm font-medium text-gray-600 dark:text-gray-300
                       bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700
                       transition-colors disabled:opacity-40"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={save}
            disabled={saving}
            className="flex-1 py-3 rounded-xl text-sm font-medium text-white transition-colors
                       disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ backgroundColor: accent }}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
