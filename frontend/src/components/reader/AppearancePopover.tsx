import React from 'react';
import {
  ReaderSettings,
  ReadingTheme,
  FontFamilyId,
  MarginOption,
  READER_THEMES,
  FONT_FAMILIES,
} from '../../types/reader';
import { Check, Columns, AlignJustify } from 'lucide-react';

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
  const currentThemeConfig = READER_THEMES[settings.theme];
  const isDark = currentThemeConfig.isDark;

  const popoverBg = isDark ? 'bg-[#2b2b2b]/95 text-neutral-100 border-white/10' : 'bg-white/95 text-neutral-900 border-black/10';
  const sectionBg = isDark ? 'bg-white/5 border-white/5' : 'bg-black/5 border-black/5';
  const labelMuted = isDark ? 'text-neutral-400' : 'text-neutral-500';
  const buttonHover = isDark ? 'hover:bg-white/10' : 'hover:bg-black/10';

  const themesList: ReadingTheme[] = ['night', 'sepia', 'white', 'gray'];
  const fontFamiliesList: FontFamilyId[] = ['serif', 'sans', 'mono', 'dyslexic'];
  const marginOptions: { id: MarginOption; label: string }[] = [
    { id: 'compact', label: 'Compact' },
    { id: 'normal', label: 'Normal' },
    { id: 'wide', label: 'Wide' },
  ];

  return (
    <div
      className={`absolute top-12 right-6 w-80 rounded-xl shadow-2xl backdrop-blur-xl border p-5 z-50 select-none animate-in fade-in zoom-in-95 duration-150 ${popoverBg}`}
      onClick={(e) => e.stopPropagation()}
    >
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-inherit">
        <h3 className="text-sm font-semibold tracking-wide">Appearance & Typography</h3>
        <button
          onClick={onClose}
          className={`text-xs px-2 py-0.5 rounded transition-colors ${buttonHover} ${labelMuted}`}
        >
          Done
        </button>
      </div>

      <div className="space-y-4 text-xs">
        {/* 1. Theme Selector (Night, Sepia, White, Gray) */}
        <div>
          <label className={`block mb-2 font-medium ${labelMuted}`}>Reading Theme</label>
          <div className="grid grid-cols-4 gap-2">
            {themesList.map((tKey) => {
              const t = READER_THEMES[tKey];
              const isSelected = settings.theme === tKey;
              return (
                <button
                  key={tKey}
                  onClick={() => onUpdateSettings({ theme: tKey })}
                  className={`flex flex-col items-center justify-center p-2 rounded-lg border transition-all ${
                    isSelected
                      ? 'ring-2 ring-primary ring-offset-1 ring-offset-black/50 border-white/60 font-semibold shadow-md'
                      : 'border-white/10 hover:border-white/30'
                  }`}
                  style={{
                    backgroundColor: t.bg,
                    color: t.text,
                  }}
                  title={t.name}
                >
                  <span className="text-[11px] mb-1 font-serif">Aa</span>
                  <span className="text-[10px] tracking-tight">{t.name}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* 2. Font Family Picker */}
        <div>
          <label className={`block mb-2 font-medium ${labelMuted}`}>Font Family</label>
          <div className="grid grid-cols-2 gap-1.5">
            {fontFamiliesList.map((fKey) => {
              const font = FONT_FAMILIES[fKey];
              const isSelected = settings.fontFamily === fKey;
              return (
                <button
                  key={fKey}
                  onClick={() => onUpdateSettings({ fontFamily: fKey })}
                  className={`flex items-center justify-between px-3 py-2 rounded-lg border text-left transition-colors ${
                    isSelected
                      ? 'bg-primary/20 border-primary text-white font-medium'
                      : `${sectionBg} hover:bg-white/10`
                  }`}
                  style={{ fontFamily: font.cssFamily }}
                >
                  <span className="text-xs truncate">{font.name}</span>
                  {isSelected && <Check size={13} className="text-primary flex-shrink-0" />}
                </button>
              );
            })}
          </div>
        </div>

        {/* 3. Font Size Slider (12px to 36px) */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className={`font-medium ${labelMuted}`}>Font Size</span>
            <span className="font-mono font-medium">{settings.fontSize}px</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-neutral-400">12px</span>
            <input
              type="range"
              min={12}
              max={36}
              step={1}
              value={settings.fontSize}
              onChange={(e) => onUpdateSettings({ fontSize: Number(e.target.value) })}
              className="flex-1 accent-primary cursor-pointer"
            />
            <span className="text-[10px] text-neutral-400">36px</span>
          </div>
        </div>

        {/* 4. Line Spacing Slider (1.2 to 2.4) */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className={`font-medium ${labelMuted}`}>Line Spacing</span>
            <span className="font-mono font-medium">{settings.lineSpacing.toFixed(1)}x</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-neutral-400">1.2</span>
            <input
              type="range"
              min={1.2}
              max={2.4}
              step={0.1}
              value={settings.lineSpacing}
              onChange={(e) => onUpdateSettings({ lineSpacing: Number(e.target.value) })}
              className="flex-1 accent-primary cursor-pointer"
            />
            <span className="text-[10px] text-neutral-400">2.4</span>
          </div>
        </div>

        {/* 5. Margins (Compact, Normal, Wide) */}
        <div>
          <label className={`block mb-1.5 font-medium ${labelMuted}`}>Page Margins</label>
          <div className="grid grid-cols-3 gap-1.5">
            {marginOptions.map((opt) => {
              const isSelected = settings.margin === opt.id;
              return (
                <button
                  key={opt.id}
                  onClick={() => onUpdateSettings({ margin: opt.id })}
                  className={`py-1.5 px-2 rounded-lg border text-center transition-colors ${
                    isSelected
                      ? 'bg-primary/20 border-primary text-white font-medium'
                      : `${sectionBg} hover:bg-white/10`
                  }`}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* 6. Spread Layout Toggle (1 vs 2 cols) */}
        <div className="pt-2 border-t border-inherit flex items-center justify-between">
          <div className="flex items-center gap-2">
            {settings.isTwoColumn ? <Columns size={16} /> : <AlignJustify size={16} />}
            <span className="font-medium">2-Column Spread</span>
          </div>
          <button
            onClick={() => onUpdateSettings({ isTwoColumn: !settings.isTwoColumn })}
            className={`w-11 h-6 flex items-center rounded-full p-1 transition-colors duration-200 cursor-pointer ${
              settings.isTwoColumn ? 'bg-primary justify-end' : 'bg-neutral-600 justify-start'
            }`}
          >
            <div className="bg-white w-4 h-4 rounded-full shadow-md" />
          </button>
        </div>
      </div>
    </div>
  );
};
