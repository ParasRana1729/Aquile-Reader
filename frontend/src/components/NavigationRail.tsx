import React from 'react';
import { Home, Library, Highlighter, Globe, Settings, BarChart2 } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

export type NavView = 'home' | 'library' | 'annotations' | 'catalogs' | 'settings' | 'insights';

interface NavigationRailProps {
  currentView: NavView;
  onSelectView: (view: NavView) => void;
}

export const NavigationRail: React.FC<NavigationRailProps> = ({
  currentView,
  onSelectView,
}) => {
  const { currentTheme } = useTheme();

  const navItems: { id: NavView; label: string; icon: React.ReactNode }[] = [
    { id: 'home', label: 'Home', icon: <Home size={20} /> },
    { id: 'library', label: 'Library', icon: <Library size={20} /> },
    { id: 'annotations', label: 'Annotations', icon: <Highlighter size={20} /> },
    { id: 'catalogs', label: 'Catalogs', icon: <Globe size={20} /> },
  ];

  const bottomItems: { id: NavView; label: string; icon: React.ReactNode }[] = [
    { id: 'settings', label: 'Settings', icon: <Settings size={20} /> },
    { id: 'insights', label: 'Reading Insights', icon: <BarChart2 size={20} /> },
  ];

  const renderButton = (item: { id: NavView; label: string; icon: React.ReactNode }) => {
    const isActive = currentView === item.id;
    return (
      <button
        key={item.id}
        onClick={() => onSelectView(item.id)}
        title={item.label}
        aria-label={item.label}
        aria-current={isActive ? 'page' : undefined}
        className="relative group w-10 h-10 my-0.5 rounded-lg flex items-center justify-center transition-all duration-150 focus:outline-none"
        style={
          isActive
            ? {
                backgroundColor: currentTheme.accent,
                color: '#ffffff',
                boxShadow: `0 4px 14px ${currentTheme.accentGlow}`,
              }
            : {}
        }
      >
        <span
          className={`flex items-center justify-center transition-colors duration-150 ${
            isActive
              ? 'text-white'
              : 'text-[#a0a0a0] group-hover:text-white group-hover:bg-white/10 w-full h-full rounded-lg flex items-center justify-center'
          }`}
        >
          {item.icon}
        </span>
      </button>
    );
  };

  return (
    <aside
      className="w-[60px] h-full flex flex-col items-center justify-between py-3 border-r border-white/5 select-none z-30 transition-colors"
      style={{
        backgroundColor: 'rgba(20, 20, 22, 0.75)',
        backdropFilter: 'blur(20px)',
      }}
    >
      {/* Top Nav Items */}
      <div className="flex flex-col items-center gap-1 w-full px-1.5">
        {navItems.map(renderButton)}
      </div>

      {/* Bottom Nav Items */}
      <div className="flex flex-col items-center gap-1 w-full px-1.5">
        {bottomItems.map(renderButton)}
      </div>
    </aside>
  );
};
