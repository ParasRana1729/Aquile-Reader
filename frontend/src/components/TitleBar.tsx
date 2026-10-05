import React, { useState, useEffect } from 'react';
import { useTheme } from '../context/ThemeContext';
import { minimizeWindow, toggleMaximizeWindow, closeWindow, isWindowMaximized } from '../utils/window';
import { ArrowLeft, Minus, Square, Copy, X } from 'lucide-react';

interface TitleBarProps {
  title?: string;
  onBack?: () => void;
  showBack?: boolean;
}

export const TitleBar: React.FC<TitleBarProps> = ({
  title = 'Aquile Reader',
  onBack,
  showBack = false,
}) => {
  const { currentTheme } = useTheme();
  const [maximized, setMaximized] = useState(false);

  useEffect(() => {
    // Check initial state
    isWindowMaximized().then(setMaximized);

    const handleResize = () => {
      isWindowMaximized().then(setMaximized);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleMinimize = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await minimizeWindow();
  };

  const handleToggleMaximize = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const isMax = await toggleMaximizeWindow();
    setMaximized(isMax);
  };

  const handleClose = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await closeWindow();
  };

  const hoverBg = currentTheme.isLight ? 'hover:bg-black/10' : 'hover:bg-white/10';

  return (
    <header
      data-tauri-drag-region
      className="h-[32px] w-full flex items-center justify-between select-none z-50 transition-colors duration-200"
      style={{
        backgroundColor: currentTheme.titlebarBg,
        color: currentTheme.titlebarText,
      }}
    >
      {/* Left Title / Back Navigation */}
      <div className="flex items-center h-full flex-shrink-0" data-tauri-drag-region>
        {showBack && onBack ? (
          <button
            onClick={onBack}
            className={`h-full px-3 flex items-center justify-center transition-colors ${hoverBg} active:opacity-70`}
            title="Back"
            data-no-drag
          >
            <ArrowLeft size={14} className="stroke-[2.5]" />
          </button>
        ) : (
          <div className="w-3" data-tauri-drag-region />
        )}
        <span
          className="text-[12px] font-normal tracking-wide flex items-center pr-4"
          data-tauri-drag-region
        >
          {title}
        </span>
      </div>

      {/* Center Draggable Spacer */}
      <div className="flex-1 h-full" data-tauri-drag-region />

      {/* Right Window Controls */}
      <div className="flex items-center h-full flex-shrink-0" data-no-drag>
        {/* Minimize */}
        <button
          onClick={handleMinimize}
          className={`w-[46px] h-full flex items-center justify-center transition-colors ${hoverBg} active:opacity-60`}
          title="Minimize"
        >
          <Minus size={12} className="stroke-[2]" />
        </button>

        {/* Maximize / Restore */}
        <button
          onClick={handleToggleMaximize}
          className={`w-[46px] h-full flex items-center justify-center transition-colors ${hoverBg} active:opacity-60`}
          title={maximized ? 'Restore' : 'Maximize'}
        >
          {maximized ? (
            <Copy size={11} className="stroke-[2] rotate-180" />
          ) : (
            <Square size={11} className="stroke-[2]" />
          )}
        </button>

        {/* Close */}
        <button
          onClick={handleClose}
          className="w-[46px] h-full flex items-center justify-center transition-colors hover:bg-[#e81123] hover:text-white active:bg-[#c4101f]"
          title="Close"
        >
          <X size={13} className="stroke-[2.2]" />
        </button>
      </div>
    </header>
  );
};
