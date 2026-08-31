// A small centred dialog over a dimmed page. Lifted out of Timeline.jsx,
// which had it privately, so the contraction confirmations can use the same
// one rather than the app growing a third hand-rolled modal.
export default function Modal({ children, onClose }) {
  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-sm w-full p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
