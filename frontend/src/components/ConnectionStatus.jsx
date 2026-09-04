// The live-sync indicator, driven by useSSE's four-state `status`. There is
// deliberately no presentation for `idle`: an anonymous visitor never opens a
// stream (the timeline is auth-gated), and rendering a red "Reconnecting..."
// at someone who isn't subscribed makes a working page look broken — on the
// very first screen a forwarded link lands on.
const PRESENTATION = {
  connecting: {
    dot: 'bg-gray-400',
    text: 'text-gray-500 dark:text-gray-400',
    label: 'Connecting...',
  },
  live: {
    dot: 'bg-green-500',
    text: 'text-green-600 dark:text-green-400',
    label: 'Live sync active',
  },
  reconnecting: {
    dot: 'bg-red-500 animate-pulse',
    text: 'text-red-600 dark:text-red-400',
    label: 'Reconnecting...',
  },
};

export default function ConnectionStatus({ status }) {
  const look = PRESENTATION[status];
  if (!look) return null;
  return (
    <div className="flex items-center gap-2" role="status">
      <div aria-hidden="true" className={`w-2 h-2 rounded-full ${look.dot}`} />
      <span className={`text-xs ${look.text}`}>{look.label}</span>
    </div>
  );
}
