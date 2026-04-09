export default function ConnectionStatus({ isConnected }) {
  return (
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full ${
        isConnected
          ? 'bg-green-500'
          : 'bg-red-500 animate-pulse'
      }`} />
      <span className={`text-xs ${
        isConnected
          ? 'text-green-600 dark:text-green-400'
          : 'text-red-600 dark:text-red-400'
      }`}>
        {isConnected ? 'Live sync active' : 'Reconnecting...'}
      </span>
    </div>
  );
}
