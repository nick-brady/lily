export default function ThemeCard({ theme, displayName, selected, onSelect }) {
  const t = theme.modes.light;
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`relative rounded-2xl overflow-hidden transition-all duration-200 text-left ${
        selected
          ? 'shadow-lg scale-[1.02]'
          : 'ring-1 ring-gray-200 dark:ring-gray-700 hover:ring-2 hover:shadow-md'
      }`}
      style={selected ? { boxShadow: `0 4px 20px ${t.accent}30` } : {}}
    >
      {/* Mini page header: real background, pattern, and display font */}
      <div
        className="h-16 flex items-center justify-center px-2"
        style={{
          backgroundColor: t.pageBg,
          backgroundImage: t.pattern,
          backgroundSize: `calc(${t.patternSize} / 1.6)`,
        }}
      >
        <span
          className="leading-tight text-center truncate"
          style={{
            fontFamily: theme.display.family,
            fontWeight: theme.display.weight,
            fontStyle: theme.display.style,
            fontSize: `calc(${t.titleSize} * 0.62)`,
            color: t.title,
          }}
        >
          {displayName}
        </span>
      </div>

      {/* Theme info */}
      <div className="bg-white dark:bg-gray-800 px-3 py-2.5 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold text-gray-800 dark:text-white leading-tight">
            {theme.label}
          </p>
          <p className="text-xs text-gray-400 leading-tight">{theme.description}</p>
        </div>
        {/* Color swatch */}
        <div
          className="h-5 w-5 rounded-full flex-shrink-0 shadow-sm"
          style={{ background: `linear-gradient(135deg, ${theme.swatch[0]}, ${theme.swatch[1]})` }}
        />
      </div>

      {/* Selected ring overlay */}
      {selected && (
        <div
          className="absolute inset-0 rounded-2xl pointer-events-none"
          style={{ outline: `2px solid ${t.accent}`, outlineOffset: '-2px' }}
        />
      )}
    </button>
  );
}
