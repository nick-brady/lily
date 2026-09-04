import useDialog from '../hooks/useDialog';

// A small centred dialog over a dimmed page. Lifted out of Timeline.jsx,
// which had it privately, so the contraction confirmations can use the same
// one rather than the app growing a third hand-rolled modal.
//
// Named by its first heading; pass `label` for a dialog without one. Focus,
// Escape and the tab ring are useDialog's job.
export default function Modal({ children, onClose, label }) {
  const panelRef = useDialog(onClose, { label });
  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        ref={panelRef}
        className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-sm w-full p-6 outline-none"
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
