import React from 'react';
import { useTheme } from '../context/ThemeContext';

interface AcrylicCanvasProps {
  children: React.ReactNode;
  showSimulatedWallpaper?: boolean;
}

export const AcrylicCanvas: React.FC<AcrylicCanvasProps> = ({
  children,
  showSimulatedWallpaper = true,
}) => {
  const { isTransparent, transparencyOpacity } = useTheme();

  const opacityDecimal = isTransparent ? transparencyOpacity / 100 : 1.0;

  return (
    <div className="relative w-full h-full overflow-hidden select-none">
      {/* Simulated Desktop Wallpaper Backdrop (Active when transparent is on) */}
      {isTransparent && showSimulatedWallpaper && (
        <div
          className="absolute inset-0 pointer-events-none z-0 overflow-hidden"
          style={{
            transform: 'translate3d(0, 0, 0)',
            backfaceVisibility: 'hidden',
          }}
        >
          {/* Deep forest misty bokeh matching Windows B0 reference screencast */}
          <div
            className="w-full h-full scale-105"
            style={{
              background: `
                radial-gradient(circle at 75% 30%, rgba(130, 160, 120, 0.45) 0%, transparent 45%),
                radial-gradient(circle at 25% 70%, rgba(45, 65, 45, 0.6) 0%, transparent 50%),
                radial-gradient(circle at 60% 80%, rgba(30, 45, 30, 0.7) 0%, transparent 60%),
                radial-gradient(circle at 85% 15%, rgba(200, 220, 190, 0.25) 0%, transparent 35%),
                linear-gradient(135deg, #18221b 0%, #202b23 35%, #141c16 70%, #0d130f 100%)
              `,
              filter: 'blur(16px)',
              transform: 'translate3d(0, 0, 0)',
            }}
          />
        </div>
      )}

      {/* Acrylic Glass Surface */}
      <div
        className="relative z-10 w-full h-full flex flex-col transition-colors duration-200"
        style={{
          backgroundColor: isTransparent
            ? `rgba(28, 28, 30, ${opacityDecimal})`
            : '#1f1f1f',
          backdropFilter: isTransparent ? 'blur(20px) saturate(140%)' : 'none',
          WebkitBackdropFilter: isTransparent ? 'blur(20px) saturate(140%)' : 'none',
          transform: 'translateZ(0)',
          contain: 'paint',
        }}
      >
        {children}
      </div>
    </div>
  );
};
