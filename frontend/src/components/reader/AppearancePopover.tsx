import React from 'react';
import {
  ReaderSettings,
  ReadingTheme,
  FontFamilyId,
  READER_THEMES,
  FONT_FAMILIES,
} from '../../types/reader';
import {
  Check,
  AlignLeft,
  AlignJustify,
  AlignCenter,
  RectangleVertical,
  BookOpen,
  X,
  Type,
} from 'lucide-react';
import { ACRYLIC_FILTER, ACRYLIC_OPACITY_PCT } from '../AcrylicCanvas';

interface AppearancePopoverProps {
  settings: ReaderSettings;
  onUpdateSettings: (updates: Partial<ReaderSettings>) => void;
  onClose: () => void;
}

export const AppearancePopover: React.FC<AppearancePopoverProps> = ({
  settings,
  onUpdateSettings,
  onClose,
}) => {
  const currentThemeConfig = READER_THEMES[settings.theme] || READER_THEMES.night;
  const isDark = currentThemeConfig.isDark;

  const popoverBg = isDark
    ? 'text-neutral-100 border-white/10 shadow-black/60'
    : 'text-neutral-900 border-black/10 shadow-black/20';
  const sectionBg = isDark ? 'bg-white/5 border-white/5' : 'bg-black/5 border-black/5';
  const labelMuted = isDark ? 'text-neutral-400' : 'text-neutral-500';
  const buttonHover = isDark ? 'hover:bg-white/10' : 'hover:bg-black/10';

  const themesList: ReadingTheme[] = ['night', 'sepia', 'white', 'gray'];

  const standardFonts: { id: FontFamilyId; label: string }[] = [
    { id: 'inter', label: 'Inter' },
    { id: 'merriweather', label: 'Merriweather' },
    { id: 'georgia', label: 'Georgia' },
    { id: 'jetbrains', label: 'JetBrains Mono' },
    { id: 'bookerly', label: 'Bookerly' },
    { id: 'literata', label: 'Literata' },
    { id: 'system', label: 'System' },
  ];

  const isDualSpread = settings.spreadMode === 'dual' || settings.isTwoColumn;
  const textAlign = settings.textAlign || 'justify';
  const marginVal = typeof settings.margin === 'number' ? settings.margin : 36;
  const letterSpacingVal = typeof settings.letterSpacing === 'number' ? settings.letterSpacing : 0;
  const paragraphSpacingVal =
    typeof settings.paragraphSpacing === 'number' ? settings.paragraphSpacing : 16;

  return (
    <div
      className={`absolute top-12 right-4 md:right-6 w-88 md:w-96 max-h-[85vh] overflow-y-auto rounded-2xl shadow-2xl acrylic-overlay overlay-pop border p-5 z-50 select-none ${popoverBg}`}
      style={{
        backgroundColor: `color-mix(in srgb, ${currentThemeConfig.toolbarBg} ${ACRYLIC_OPACITY_PCT}%, transparent)`,
        backdropFilter: ACRYLIC_FILTER,
        WebkitBackdropFilter: ACRYLIC_FILTER,
      }}
      onClick={(e) => e.stopPropagation()}
    >
      {/* Header */}
      <div className="flex items-center justify-between pb-3 mb-4 border-b border-inherit">
        <div className="flex items-center gap-2">
          <Type size={16} className="text-primary" />
          <h3 className="text-sm font-semibold tracking-wide">Appearance & Typography</h3>
        </div>
        <button
          onClick={onClose}
          className={`p-1 rounded-md transition-colors duration-150 ease-out ${buttonHover} ${labelMuted}`}
          title="Close appearance settings"
          aria-label="Close appearance settings"
        >
          <X size={15} />
        </button>
      </div>

      <div className="space-y-4 text-xs">
        {/* 1. Page Spread Mode (Single Column vs Two-Page Spread) */}
        <div>
          <label className={`block mb-1.5 font-medium ${labelMuted}`}>Spread Layout</label>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() =>
                onUpdateSettings({
                  spreadMode: 'single',
                  isTwoColumn: false,
                })
              }
              aria-pressed={!isDualSpread}
              className={`flex items-center justify-center gap-2 py-2 px-3 rounded-lg border text-xs font-medium transition-all duration-150 ease-out ${
                !isDualSpread
                  ? 'bg-primary/20 border-primary text-primary shadow-xs'
                  : `${sectionBg} ${buttonHover} ${labelMuted}`
              }`}
            >
              <RectangleVertical size={15} />
              <span>Single Column</span>
            </button>
            <button
              type="button"
              onClick={() =>
                onUpdateSettings({
                  spreadMode: 'dual',
                  isTwoColumn: true,
                })
              }
              aria-pressed={isDualSpread}
              className={`flex items-center justify-center gap-2 py-2 px-3 rounded-lg border text-xs font-medium transition-all duration-150 ease-out ${
                isDualSpread
                  ? 'bg-primary/20 border-primary text-primary shadow-xs'
                  : `${sectionBg} ${buttonHover} ${labelMuted}`
              }`}
            >
              <BookOpen size={15} />
              <span>Two-Page Spread</span>
            </button>
          </div>
        </div>

        {/* 2. Reading Theme */}
        <div>
          <label className={`block mb-1.5 font-medium ${labelMuted}`}>Color Theme</label>
          <div className="grid grid-cols-4 gap-2">
            {themesList.map((tKey) => {
              const t = READER_THEMES[tKey];
              const isSelected = settings.theme === tKey;
              return (
                <button
                  key={tKey}
                  onClick={() => onUpdateSettings({ theme: tKey })}
                  aria-pressed={isSelected}
                  className={`flex flex-col items-center justify-center p-2 rounded-lg border transition-all duration-150 ease-out ${
                    isSelected
                      ? 'ring-2 ring-primary ring-offset-1 ring-offset-black/50 border-white/60 font-semibold shadow-md'
                      : isDark
                      ? 'border-white/10 hover:border-white/30'
                      : 'border-black/10 hover:border-black/30'
                  }`}
                  style={{
                    backgroundColor: t.bg,
                    color: t.text,
                  }}
                  title={t.name}
                >
                  <span className="text-[11px] mb-0.5 font-serif font-bold">Aa</span>
                  <span className="text-[10px] tracking-tight">{t.name}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* 3. Text Alignment */}
        <div>
          <label className={`block mb-1.5 font-medium ${labelMuted}`}>Text Alignment</label>
          <div className="grid grid-cols-3 gap-1.5">
            <button
              type="button"
              onClick={() => onUpdateSettings({ textAlign: 'left' })}
              aria-pressed={textAlign === 'left'}
              className={`flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg border transition-colors duration-150 ease-out ${
                textAlign === 'left'
                  ? 'bg-primary/20 border-primary text-primary font-medium'
                  : `${sectionBg} ${buttonHover} ${labelMuted}`
              }`}
              title="Align Left"
            >
              <AlignLeft size={14} />
              <span>Left</span>
            </button>
            <button
              type="button"
              onClick={() => onUpdateSettings({ textAlign: 'justify' })}
              aria-pressed={textAlign === 'justify'}
              className={`flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg border transition-colors duration-150 ease-out ${
                textAlign === 'justify'
                  ? 'bg-primary/20 border-primary text-primary font-medium'
                  : `${sectionBg} ${buttonHover} ${labelMuted}`
              }`}
              title="Justify Text"
            >
              <AlignJustify size={14} />
              <span>Justify</span>
            </button>
            <button
              type="button"
              onClick={() => onUpdateSettings({ textAlign: 'center' })}
              aria-pressed={textAlign === 'center'}
              className={`flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg border transition-colors duration-150 ease-out ${
                textAlign === 'center'
                  ? 'bg-primary/20 border-primary text-primary font-medium'
                  : `${sectionBg} ${buttonHover} ${labelMuted}`
              }`}
              title="Align Center"
            >
              <AlignCenter size={14} />
              <span>Center</span>
            </button>
          </div>
        </div>

        {/* 4. Font Picker */}
        <div>
          <label className={`block mb-1.5 font-medium ${labelMuted}`}>Typeface</label>
          <div className="grid grid-cols-2 gap-1.5 mb-2">
            {standardFonts.map((item) => {
              const font = FONT_FAMILIES[item.id];
              const isSelected =
                (!settings.customFont || !settings.customFont.trim()) &&
                (settings.fontFamily === item.id ||
                  (item.id === 'merriweather' && settings.fontFamily === 'serif') ||
                  (item.id === 'inter' && settings.fontFamily === 'sans') ||
                  (item.id === 'jetbrains' && settings.fontFamily === 'mono'));

              return (
                <button
                  key={item.id}
                  onClick={() =>
                    onUpdateSettings({
                      fontFamily: item.id,
                      customFont: '',
                    })
                  }
                  className={`flex items-center justify-between px-2.5 py-2 rounded-lg border text-left transition-colors duration-150 ease-out ${
                    isSelected
                      ? 'bg-primary/20 border-primary text-primary font-medium'
                      : `${sectionBg} ${buttonHover}`
                  }`}
                  style={{ fontFamily: font?.cssFamily }}
                  aria-pressed={isSelected}
                >
                  <span className="text-xs truncate">{item.label}</span>
                  {isSelected && <Check size={13} className="text-primary flex-shrink-0" />}
                </button>
              );
            })}
          </div>

          {/* Optional Custom Font Input */}
          <div className="pt-1">
            <div className="relative">
              <input
                type="text"
                value={settings.customFont || ''}
                onChange={(e) => onUpdateSettings({ customFont: e.target.value })}
                placeholder="Or enter custom font (e.g. Roboto, Lora)"
                aria-label="Custom font name"
                className={`w-full px-3 py-1.5 rounded-lg border text-xs transition-colors duration-150 ease-out focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--accent-color)] ${
                  isDark
                    ? 'bg-black/30 border-white/10 text-white placeholder-neutral-500 focus:border-primary'
                    : 'bg-white border-black/10 text-black placeholder-neutral-400 focus:border-primary'
                }`}
              />
              {settings.customFont && (
                <button
                  type="button"
                  onClick={() => onUpdateSettings({ customFont: '' })}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-white transition-colors duration-150 ease-out"
                  title="Clear custom font"
                  aria-label="Clear custom font"
                >
                  <X size={12} />
                </button>
              )}
            </div>
            {settings.customFont?.trim() && (
              <p className="text-[10px] text-primary mt-1 font-sans">
                Active custom font: &ldquo;{settings.customFont}&rdquo;
              </p>
            )}
          </div>
        </div>

        {/* 5. Fine-Tuning Sliders */}
        <div className="pt-3 border-t border-inherit space-y-3.5">
          {/* Font Size (12px to 36px) */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className={`font-medium ${labelMuted}`}>Font Size</span>
              <span className="font-mono font-medium">{settings.fontSize}px</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-neutral-400 w-6">12px</span>
              <input
                type="range"
                min={12}
                max={36}
                step={1}
                value={settings.fontSize}
                onChange={(e) => onUpdateSettings({ fontSize: Number(e.target.value) })}
                aria-label="Font size"
                className="flex-1 accent-primary cursor-pointer"
              />
              <span className="text-[10px] text-neutral-400 w-6 text-right">36px</span>
            </div>
          </div>

          {/* Margins (16px to 120px) */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className={`font-medium ${labelMuted}`}>Margins</span>
              <span className="font-mono font-medium">{marginVal}px</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-neutral-400 w-6">16px</span>
              <input
                type="range"
                min={16}
                max={120}
                step={2}
                value={marginVal}
                onChange={(e) => onUpdateSettings({ margin: Number(e.target.value) })}
                aria-label="Margins"
                className="flex-1 accent-primary cursor-pointer"
              />
              <span className="text-[10px] text-neutral-400 w-6 text-right">120px</span>
            </div>
          </div>

          {/* Line Spacing (1.2 to 2.4) */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className={`font-medium ${labelMuted}`}>Line Spacing</span>
              <span className="font-mono font-medium">{settings.lineSpacing.toFixed(1)}x</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-neutral-400 w-6">1.2</span>
              <input
                type="range"
                min={1.2}
                max={2.4}
                step={0.05}
                value={settings.lineSpacing}
                onChange={(e) => onUpdateSettings({ lineSpacing: Number(e.target.value) })}
                aria-label="Line spacing"
                className="flex-1 accent-primary cursor-pointer"
              />
              <span className="text-[10px] text-neutral-400 w-6 text-right">2.4</span>
            </div>
          </div>

          {/* Letter Spacing (-0.5px to 3.0px) */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className={`font-medium ${labelMuted}`}>Letter Spacing</span>
              <span className="font-mono font-medium">{letterSpacingVal.toFixed(1)}px</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-neutral-400 w-6">-0.5</span>
              <input
                type="range"
                min={-0.5}
                max={3.0}
                step={0.1}
                value={letterSpacingVal}
                onChange={(e) => onUpdateSettings({ letterSpacing: Number(e.target.value) })}
                aria-label="Letter spacing"
                className="flex-1 accent-primary cursor-pointer"
              />
              <span className="text-[10px] text-neutral-400 w-6 text-right">3.0</span>
            </div>
          </div>

          {/* Paragraph Spacing (0px to 24px) */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className={`font-medium ${labelMuted}`}>Paragraph Spacing</span>
              <span className="font-mono font-medium">{paragraphSpacingVal}px</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-neutral-400 w-6">0px</span>
              <input
                type="range"
                min={0}
                max={24}
                step={1}
                value={paragraphSpacingVal}
                onChange={(e) => onUpdateSettings({ paragraphSpacing: Number(e.target.value) })}
                aria-label="Paragraph spacing"
                className="flex-1 accent-primary cursor-pointer"
              />
              <span className="text-[10px] text-neutral-400 w-6 text-right">24px</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
