import React, { useState, useEffect } from 'react';
import { useTheme } from '../context/ThemeContext';
import { COLOR_THEMES, ThemeId } from '../types/theme';
import { InsightsView } from './InsightsView';
import {
  BookOpen,
  Sliders,
  FolderSync,
  Palette,
  HardDriveDownload,
  Cloud,
  BarChart2,
  HelpCircle,
  FileText,
  Info,
  Plus,
  Check,
  Folder,
  RefreshCw,
  ExternalLink,
  ChevronRight,
  ChevronDown,
  Trash2,
  CheckSquare,
  Square,
  Shield,
  Star,
  MessageSquare,
  Share2,
  HelpCircle as QuestionIcon,
} from 'lucide-react';

type SettingsCategory =
  | 'reader'
  | 'general'
  | 'sync-folders'
  | 'personalization'
  | 'backup'
  | 'cloud-sync'
  | 'insights'
  | 'faq'
  | 'changelog'
  | 'about';

interface SyncFolderItem {
  id: string;
  path: string;
  bookCount: number;
  lastSynced: string;
  status: 'idle' | 'syncing';
}

interface SettingsViewProps {
  onBackToHome?: () => void;
  initialCategory?: SettingsCategory;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  initialCategory = 'reader',
}) => {
  const {
    currentTheme,
    themeId,
    setTheme,
    isTransparent,
    setIsTransparent,
    transparencyOpacity,
    setTransparencyOpacity,
  } = useTheme();

  const [activeCategory, setActiveCategory] = useState<SettingsCategory>(initialCategory);

  // --- Reader Settings State ---
  const [standardizeMargins, setStandardizeMargins] = useState(() => {
    return localStorage.getItem('aquile_setting_std_margins') === 'true';
  });
  const [overrideAlignment, setOverrideAlignment] = useState(() => {
    return localStorage.getItem('aquile_setting_override_align') === 'true';
  });
  const [autoSwitchColumns, setAutoSwitchColumns] = useState(() => {
    return localStorage.getItem('aquile_setting_auto_columns') === 'true';
  });
  const [readAloudAutoScroll, setReadAloudAutoScroll] = useState(() => {
    const val = localStorage.getItem('aquile_setting_readaloud_scroll');
    return val !== null ? val === 'true' : true;
  });
  const [searchEngine, setSearchEngine] = useState(() => {
    return localStorage.getItem('aquile_setting_search_engine') || 'Bing';
  });
  const [dictionary, setDictionary] = useState(() => {
    return localStorage.getItem('aquile_setting_dictionary') || 'Default dictionary [en-US]';
  });
  const [pageTransition, setPageTransition] = useState(() => {
    return localStorage.getItem('aquile_setting_page_transition') || 'None';
  });

  // Experimental Reader Toggles
  const [enhancedRendering, setEnhancedRendering] = useState(() => {
    return localStorage.getItem('aquile_exp_enhanced_rendering') === 'true';
  });
  const [useBookFonts, setUseBookFonts] = useState(() => {
    return localStorage.getItem('aquile_exp_book_fonts') === 'true';
  });
  const [improvedTouchpad, setImprovedTouchpad] = useState(() => {
    return localStorage.getItem('aquile_exp_touchpad') === 'true';
  });
  const [modernEpubEngine, setModernEpubEngine] = useState(() => {
    return localStorage.getItem('aquile_exp_modern_epub') === 'true';
  });

  // --- General Settings State ---
  const [showBookTitles, setShowBookTitles] = useState(() => {
    return localStorage.getItem('aquile_setting_show_titles') === 'true';
  });
  const [displayLanguage, setDisplayLanguage] = useState(() => {
    return localStorage.getItem('aquile_setting_display_lang') || 'English';
  });
  const [tutorialResetMessage, setTutorialResetMessage] = useState<string | null>(null);

  // --- Sync Folders State ---
  const [syncFolders, setSyncFolders] = useState<SyncFolderItem[]>(() => {
    const saved = localStorage.getItem('aquile_sync_folders');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        // ignore
      }
    }
    return [
      {
        id: 'sf-1',
        path: '/home/paras/Documents/Books',
        bookCount: 4,
        lastSynced: 'Just now',
        status: 'idle',
      },
    ];
  });
  const [isSyncingAll, setIsSyncingAll] = useState(false);
  const [newFolderPath, setNewFolderPath] = useState('');
  const [isAddFolderModalOpen, setIsAddFolderModalOpen] = useState(false);

  // --- Backup & Restore State ---
  const [backupOperation, setBackupOperation] = useState<'backup' | 'restore'>('backup');
  const [backupConfigs, setBackupConfigs] = useState({
    bookFiles: true,
    metadata: true,
    notesHighlights: true,
    bookmarks: true,
    favorites: true,
  });
  const [backupStoragePath, setBackupStoragePath] = useState(
    '/home/paras/Documents/AquileReader_Backups'
  );
  const [backupLogs, setBackupLogs] = useState<string[]>([
    'Ready for operation.',
  ]);
  const [isBackupRunning, setIsBackupRunning] = useState(false);

  // --- Cloud Sync State ---
  const [isGoogleLinked, setIsGoogleLinked] = useState(() => {
    return localStorage.getItem('aquile_cloud_linked') === 'true';
  });
  const [enableCloudSync, setEnableCloudSync] = useState(() => {
    return localStorage.getItem('aquile_cloud_enabled') === 'true';
  });
  const [useAltSignIn, setUseAltSignIn] = useState(() => {
    return localStorage.getItem('aquile_cloud_alt_signin') === 'true';
  });
  const [syncMode, setSyncMode] = useState<'all' | 'selected'>(() => {
    return (localStorage.getItem('aquile_cloud_mode') as 'all' | 'selected') || 'all';
  });
  const [cloudSyncStatus, setCloudSyncStatus] = useState<string | null>(null);

  // --- FAQ State ---
  const [expandedFaqId, setExpandedFaqId] = useState<number | null>(0);

  // Save changes to localStorage
  const updateSetting = (key: string, val: boolean | string) => {
    localStorage.setItem(key, String(val));
  };

  // Helper toggle switch matching Windows B0
  const renderToggle = (
    label: string,
    description: string | null,
    checked: boolean,
    onChange: (val: boolean) => void
  ) => (
    <div className="flex items-center justify-between py-3 max-w-2xl">
      <div className="pr-6">
        <div className="text-[14px] font-medium text-neutral-100">{label}</div>
        {description && (
          <div className="text-[12px] text-neutral-400 mt-0.5 leading-snug">{description}</div>
        )}
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <button
          type="button"
          role="switch"
          aria-checked={checked}
          onClick={() => onChange(!checked)}
          className="relative inline-flex h-5 w-10 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none"
          style={{
            backgroundColor: checked ? currentTheme.accent : '#404044',
          }}
        >
          <span
            className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-md ring-0 transition duration-200 ease-in-out ${
              checked ? 'translate-x-5' : 'translate-x-0'
            }`}
          />
        </button>
        <span className="text-[13px] text-neutral-300 w-16 select-none">
          {checked ? 'Enabled' : 'Disabled'}
        </span>
      </div>
    </div>
  );

  const categories = [
    { id: 'reader', label: 'Reader', icon: <BookOpen size={16} /> },
    { id: 'general', label: 'General', icon: <Sliders size={16} /> },
    { id: 'sync-folders', label: 'Sync folders', icon: <FolderSync size={16} /> },
    { id: 'personalization', label: 'Personalization', icon: <Palette size={16} /> },
    { id: 'backup', label: 'Backup & Restore', icon: <HardDriveDownload size={16} /> },
    { id: 'cloud-sync', label: 'Cloud sync', icon: <Cloud size={16} /> },
    { id: 'insights', label: 'Reading insights', icon: <BarChart2 size={16} /> },
  ];

  const secondaryCategories = [
    { id: 'faq', label: 'Frequently asked questions', icon: <HelpCircle size={16} /> },
    { id: 'changelog', label: 'Change log', icon: <FileText size={16} /> },
    { id: 'about', label: 'About us', icon: <Info size={16} /> },
  ];

  // Backup execution simulation
  const handleExecuteBackupRestore = () => {
    setIsBackupRunning(true);
    const time = new Date().toLocaleTimeString();
    if (backupOperation === 'backup') {
      setBackupLogs((prev) => [
        `[${time}] Starting backup operation to: ${backupStoragePath}...`,
        ...prev,
      ]);
      setTimeout(() => {
        setBackupLogs((prev) => [
          `[${new Date().toLocaleTimeString()}] Archiving ${backupConfigs.bookFiles ? 'books, ' : ''}${backupConfigs.metadata ? 'metadata, ' : ''}${backupConfigs.notesHighlights ? 'annotations' : ''}...`,
          ...prev,
        ]);
      }, 600);
      setTimeout(() => {
        setBackupLogs((prev) => [
          `[${new Date().toLocaleTimeString()}] ✓ Backup created successfully: aquile_backup_${Date.now()}.zip (14.2 MB)`,
          ...prev,
        ]);
        setIsBackupRunning(false);
      }, 1400);
    } else {
      setBackupLogs((prev) => [
        `[${time}] Inspecting archive at: ${backupStoragePath}...`,
        ...prev,
      ]);
      setTimeout(() => {
        setBackupLogs((prev) => [
          `[${new Date().toLocaleTimeString()}] Validating configuration schemas and checksums...`,
          ...prev,
        ]);
      }, 600);
      setTimeout(() => {
        setBackupLogs((prev) => [
          `[${new Date().toLocaleTimeString()}] ✓ Restore completed. 4 books and 12 annotations restored.`,
          ...prev,
        ]);
        setIsBackupRunning(false);
      }, 1400);
    }
  };

  // Sync folders execution
  const handleSyncNow = () => {
    setIsSyncingAll(true);
    setTimeout(() => {
      setSyncFolders((prev) =>
        prev.map((f) => ({
          ...f,
          lastSynced: 'Just now',
          status: 'idle',
        }))
      );
      setIsSyncingAll(false);
    }, 1200);
  };

  const handleAddSyncFolder = () => {
    if (!newFolderPath.trim()) return;
    const item: SyncFolderItem = {
      id: `sf-${Date.now()}`,
      path: newFolderPath.trim(),
      bookCount: 0,
      lastSynced: 'Never',
      status: 'idle',
    };
    const updated = [...syncFolders, item];
    setSyncFolders(updated);
    localStorage.setItem('aquile_sync_folders', JSON.stringify(updated));
    setNewFolderPath('');
    setIsAddFolderModalOpen(false);
  };

  const handleRemoveSyncFolder = (id: string) => {
    const updated = syncFolders.filter((f) => f.id !== id);
    setSyncFolders(updated);
    localStorage.setItem('aquile_sync_folders', JSON.stringify(updated));
  };

  return (
    <div className="flex h-full w-full select-none overflow-hidden">
      {/* Settings Sub-Navigation Sidebar (matching win_024–win_044) */}
      <nav className="w-60 h-full flex flex-col border-r border-white/5 bg-black/25 backdrop-blur-md px-3 py-4 flex-shrink-0">
        <div className="flex items-center gap-3 px-3 mb-6">
          <span className="text-[18px] font-semibold tracking-tight text-white">
            Settings
          </span>
        </div>

        <div className="flex-1 space-y-1 overflow-y-auto pr-1">
          {categories.map((cat) => {
            const isActive = activeCategory === cat.id;
            return (
              <button
                key={cat.id}
                onClick={() => setActiveCategory(cat.id as SettingsCategory)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-md text-[13px] font-normal transition-all relative ${
                  isActive
                    ? 'bg-white/10 text-white font-medium'
                    : 'text-neutral-300 hover:bg-white/5 hover:text-white'
                }`}
              >
                {isActive && (
                  <span
                    className="absolute left-0 top-1.5 bottom-1.5 w-1 rounded-r"
                    style={{ backgroundColor: currentTheme.accent }}
                  />
                )}
                <span className={isActive ? 'text-white' : 'text-neutral-400'}>
                  {cat.icon}
                </span>
                <span>{cat.label}</span>
              </button>
            );
          })}

          <div className="pt-4 pb-2">
            <div className="h-px bg-white/10 mx-2 my-2" />
          </div>

          {secondaryCategories.map((cat) => {
            const isActive = activeCategory === cat.id;
            return (
              <button
                key={cat.id}
                onClick={() => setActiveCategory(cat.id as SettingsCategory)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-md text-[13px] font-normal transition-all relative ${
                  isActive
                    ? 'bg-white/10 text-white font-medium'
                    : 'text-neutral-300 hover:bg-white/5 hover:text-white'
                }`}
              >
                {isActive && (
                  <span
                    className="absolute left-0 top-1.5 bottom-1.5 w-1 rounded-r"
                    style={{ backgroundColor: currentTheme.accent }}
                  />
                )}
                <span className={isActive ? 'text-white' : 'text-neutral-400'}>
                  {cat.icon}
                </span>
                <span>{cat.label}</span>
              </button>
            );
          })}
        </div>
      </nav>

      {/* Settings Content Pane */}
      <main className="flex-1 h-full overflow-y-auto px-10 py-8 bg-transparent">
        {/* ============================================================ */}
        {/* 1. READER SETTINGS (win_024 - win_026)                       */}
        {/* ============================================================ */}
        {activeCategory === 'reader' && (
          <div className="space-y-6 max-w-3xl pb-16">
            <h1 className="text-[22px] font-semibold text-white tracking-tight">
              Reader Settings
            </h1>

            <div className="space-y-1 divide-y divide-white/5">
              {renderToggle(
                'Standardize margins',
                'Overrides any margin specified in the book to provide consistent layout in the reader',
                standardizeMargins,
                (val) => {
                  setStandardizeMargins(val);
                  updateSetting('aquile_setting_std_margins', val);
                }
              )}

              {renderToggle(
                'Override text alignment',
                'Overrides any text alignment preference set in the book to provide consistent layout in the reader',
                overrideAlignment,
                (val) => {
                  setOverrideAlignment(val);
                  updateSetting('aquile_setting_override_align', val);
                }
              )}

              {renderToggle(
                'Auto switch to 1 column layout',
                'In 2-column layout when device rotates to portrait mode, reader will auto switch to 1-column layout, and vice versa',
                autoSwitchColumns,
                (val) => {
                  setAutoSwitchColumns(val);
                  updateSetting('aquile_setting_auto_columns', val);
                }
              )}

              {renderToggle(
                'ReadAloud auto-scroll',
                'Auto scrolls the page to follow the sentence being read in the ReadAloud mode',
                readAloudAutoScroll,
                (val) => {
                  setReadAloudAutoScroll(val);
                  updateSetting('aquile_setting_readaloud_scroll', val);
                }
              )}
            </div>

            {/* Selectors */}
            <div className="space-y-4 pt-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 max-w-2xl py-2">
                <div>
                  <div className="text-[14px] font-medium text-neutral-100">Search engine</div>
                  <div className="text-[12px] text-neutral-400">Search engine to use for web search</div>
                </div>
                <div className="relative w-48">
                  <select
                    value={searchEngine}
                    onChange={(e) => {
                      setSearchEngine(e.target.value);
                      updateSetting('aquile_setting_search_engine', e.target.value);
                    }}
                    className="w-full appearance-none bg-neutral-800/80 border border-white/10 rounded px-3 py-1.5 text-[13px] text-white focus:outline-none focus:border-neutral-400 cursor-pointer"
                  >
                    <option value="Bing">Bing</option>
                    <option value="Google">Google</option>
                    <option value="DuckDuckGo">DuckDuckGo</option>
                  </select>
                  <ChevronDown size={14} className="absolute right-2.5 top-2.5 pointer-events-none text-neutral-400" />
                </div>
              </div>

              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 max-w-2xl py-2">
                <div>
                  <div className="text-[14px] font-medium text-neutral-100">Dictionary</div>
                  <div className="text-[12px] text-neutral-400">Preferred dictionary for the reader</div>
                </div>
                <div className="relative w-56">
                  <select
                    value={dictionary}
                    onChange={(e) => {
                      setDictionary(e.target.value);
                      updateSetting('aquile_setting_dictionary', e.target.value);
                    }}
                    className="w-full appearance-none bg-neutral-800/80 border border-white/10 rounded px-3 py-1.5 text-[13px] text-white focus:outline-none focus:border-neutral-400 cursor-pointer"
                  >
                    <option value="Default dictionary [en-US]">Default dictionary [en-US]</option>
                    <option value="Oxford English">Oxford English</option>
                    <option value="Wiktionary">Wiktionary</option>
                    <option value="Webster's 1913">Webster's 1913</option>
                  </select>
                  <ChevronDown size={14} className="absolute right-2.5 top-2.5 pointer-events-none text-neutral-400" />
                </div>
              </div>

              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 max-w-2xl py-2">
                <div>
                  <div className="text-[14px] font-medium text-neutral-100">Page transition style</div>
                  <div className="text-[12px] text-neutral-400">Animation for page change</div>
                </div>
                <div className="relative w-48">
                  <select
                    value={pageTransition}
                    onChange={(e) => {
                      setPageTransition(e.target.value);
                      updateSetting('aquile_setting_page_transition', e.target.value);
                    }}
                    className="w-full appearance-none bg-neutral-800/80 border border-white/10 rounded px-3 py-1.5 text-[13px] text-white focus:outline-none focus:border-neutral-400 cursor-pointer"
                  >
                    <option value="None">None</option>
                    <option value="Slide">Slide</option>
                    <option value="Fade">Fade</option>
                    <option value="Flip">Flip</option>
                  </select>
                  <ChevronDown size={14} className="absolute right-2.5 top-2.5 pointer-events-none text-neutral-400" />
                </div>
              </div>
            </div>

            {/* Experimental Section (matching win_025 / win_026) */}
            <div className="pt-6 space-y-3">
              <h2 className="text-[18px] font-semibold text-white">Experimental</h2>
              <p className="text-[13px] text-neutral-400 max-w-2xl">
                These features are still in development and might be little unstable or buggy. You can try them out and share feedback with us.
              </p>
              <div>
                <a
                  href="#issues"
                  onClick={(e) => e.preventDefault()}
                  className="text-[13px] hover:underline"
                  style={{ color: currentTheme.accent }}
                >
                  More details and known issues
                </a>
              </div>

              <div className="space-y-1 divide-y divide-white/5 pt-2">
                {renderToggle(
                  'Enhanced rendering',
                  'Improves the format/layout in which books are rendered for reading',
                  enhancedRendering,
                  (val) => {
                    setEnhancedRendering(val);
                    updateSetting('aquile_exp_enhanced_rendering', val);
                  }
                )}

                {renderToggle(
                  "Use book's fonts",
                  'Reader uses the original fonts packaged with the book',
                  useBookFonts,
                  (val) => {
                    setUseBookFonts(val);
                    updateSetting('aquile_exp_book_fonts', val);
                  }
                )}

                {renderToggle(
                  'Improved touchpad scrolling',
                  'Fixes the multiple pages getting changed issue when using touchpad',
                  improvedTouchpad,
                  (val) => {
                    setImprovedTouchpad(val);
                    updateSetting('aquile_exp_touchpad', val);
                  }
                )}

                {renderToggle(
                  'Modern EPUB render engine',
                  'Applied the next time an EPUB is opened. Turn off if Modern engine causes any issues or regressions.',
                  modernEpubEngine,
                  (val) => {
                    setModernEpubEngine(val);
                    updateSetting('aquile_exp_modern_epub', val);
                  }
                )}
              </div>
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* 2. GENERAL SETTINGS (win_029)                                */}
        {/* ============================================================ */}
        {activeCategory === 'general' && (
          <div className="space-y-6 max-w-3xl">
            <h1 className="text-[22px] font-semibold text-white tracking-tight">
              General Settings
            </h1>

            <div className="space-y-2 divide-y divide-white/5">
              {renderToggle(
                'Show book titles',
                'Display title for all books in the library view',
                showBookTitles,
                (val) => {
                  setShowBookTitles(val);
                  updateSetting('aquile_setting_show_titles', val);
                }
              )}
            </div>

            {/* Reset tutorials */}
            <div className="pt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 max-w-2xl py-2">
              <div>
                <div className="text-[14px] font-medium text-neutral-100">Reset tutorials</div>
                <div className="text-[12px] text-neutral-400">Show all the tutorials again</div>
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => {
                    localStorage.removeItem('aquile_seen_tutorial');
                    setTutorialResetMessage('Tutorials have been reset.');
                    setTimeout(() => setTutorialResetMessage(null), 3000);
                  }}
                  className="px-4 py-1.5 rounded bg-neutral-800 hover:bg-neutral-700 text-white text-[13px] border border-white/10 transition-colors"
                >
                  Reset
                </button>
                {tutorialResetMessage && (
                  <span className="text-[12px] text-emerald-400">{tutorialResetMessage}</span>
                )}
              </div>
            </div>

            {/* Display language */}
            <div className="pt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 max-w-2xl py-2">
              <div>
                <div className="text-[14px] font-medium text-neutral-100">Display language</div>
                <div className="text-[12px] text-neutral-400">
                  Buttons, menus and other controls will show in this language. This setting will be applied on the next start of the app.
                </div>
              </div>
              <div className="flex flex-col items-end gap-1.5">
                <div className="relative w-44">
                  <select
                    value={displayLanguage}
                    onChange={(e) => {
                      setDisplayLanguage(e.target.value);
                      updateSetting('aquile_setting_display_lang', e.target.value);
                    }}
                    className="w-full appearance-none bg-neutral-800/80 border border-white/10 rounded px-3 py-1.5 text-[13px] text-white focus:outline-none focus:border-neutral-400 cursor-pointer"
                  >
                    <option value="English">English</option>
                    <option value="Español">Español</option>
                    <option value="Français">Français</option>
                    <option value="Deutsch">Deutsch</option>
                    <option value="Italiano">Italiano</option>
                    <option value="Português">Português</option>
                    <option value="Русский">Русский</option>
                    <option value="中文">中文</option>
                    <option value="日本語">日本語</option>
                    <option value="한국어">한국어</option>
                  </select>
                  <ChevronDown size={14} className="absolute right-2.5 top-2.5 pointer-events-none text-neutral-400" />
                </div>
                <a
                  href="#translate"
                  onClick={(e) => e.preventDefault()}
                  className="text-[12px] hover:underline"
                  style={{ color: currentTheme.accent }}
                >
                  Help translate to more languages
                </a>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* 3. SYNC FOLDERS (win_031)                                    */}
        {/* ============================================================ */}
        {activeCategory === 'sync-folders' && (
          <div className="space-y-6 max-w-3xl">
            <h1 className="text-[22px] font-semibold text-white tracking-tight">
              Sync Folders
            </h1>

            <p className="text-[13px] text-neutral-300 leading-relaxed max-w-2xl">
              Aquile Reader on app start-up syncs books from 'Sync Folders' and automatically add/remove books from the app library. This provides an easy way to keep the Aquile Reader library and your local book collection in sync.
            </p>

            <div className="flex items-center gap-3 pt-2">
              <button
                type="button"
                onClick={handleSyncNow}
                disabled={isSyncingAll}
                className="px-4 py-2 rounded-md bg-white/10 hover:bg-white/15 text-white text-[13px] font-medium flex items-center gap-2 border border-white/10 transition-colors disabled:opacity-50"
              >
                <RefreshCw size={14} className={isSyncingAll ? 'animate-spin' : ''} />
                <span>{isSyncingAll ? 'Syncing...' : 'Sync now'}</span>
              </button>

              <button
                type="button"
                onClick={() => setIsAddFolderModalOpen(true)}
                className="px-4 py-2 rounded-md bg-white/10 hover:bg-white/15 text-white text-[13px] font-medium flex items-center gap-2 border border-white/10 transition-colors"
              >
                <Plus size={15} />
                <span>Add sync folder</span>
              </button>
            </div>

            {/* Configured Folders List */}
            <div className="space-y-3 pt-4">
              <h2 className="text-[15px] font-medium text-neutral-200">
                Configured Folders ({syncFolders.length})
              </h2>

              <div className="space-y-2 max-w-2xl">
                {syncFolders.map((sf) => (
                  <div
                    key={sf.id}
                    className="p-3.5 rounded-lg bg-black/30 border border-white/10 flex items-center justify-between"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <Folder size={18} style={{ color: currentTheme.accent }} className="shrink-0" />
                      <div className="min-w-0">
                        <div className="text-[13px] font-medium text-white truncate font-mono">
                          {sf.path}
                        </div>
                        <div className="text-[11px] text-neutral-400 mt-0.5">
                          {sf.bookCount} books tracked • Last synced: {sf.lastSynced}
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveSyncFolder(sf.id)}
                      className="p-2 text-neutral-400 hover:text-red-400 transition-colors shrink-0"
                      title="Remove folder from sync"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Add folder modal */}
            {isAddFolderModalOpen && (
              <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
                <div className="bg-[#1e1e20] border border-white/15 rounded-xl p-6 max-w-md w-full shadow-2xl space-y-4">
                  <h3 className="text-[16px] font-semibold text-white">Add Sync Folder</h3>
                  <p className="text-[12px] text-neutral-400">
                    Enter the path to your local directory containing EPUB, PDF, or Comic files:
                  </p>
                  <input
                    type="text"
                    value={newFolderPath}
                    onChange={(e) => setNewFolderPath(e.target.value)}
                    placeholder="/home/user/Books or ~/Documents/Books"
                    className="w-full bg-black/50 border border-white/15 rounded px-3 py-2 text-[13px] text-white focus:outline-none focus:border-neutral-400 font-mono"
                  />
                  <div className="flex justify-end gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setIsAddFolderModalOpen(false)}
                      className="px-3 py-1.5 rounded text-[13px] text-neutral-300 hover:bg-white/10"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleAddSyncFolder}
                      className="px-4 py-1.5 rounded text-[13px] text-white font-medium shadow"
                      style={{ backgroundColor: currentTheme.accent }}
                    >
                      Add Folder
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ============================================================ */}
        {/* 4. PERSONALIZATION (win_032 - win_041)                       */}
        {/* ============================================================ */}
        {activeCategory === 'personalization' && (
          <div className="space-y-8 max-w-4xl pb-16">
            <h1 className="text-[22px] font-semibold text-white tracking-tight">
              Personalization
            </h1>

            {/* Transparent Background Toggle */}
            <div className="space-y-1">
              {renderToggle(
                'Transparent background',
                'Enable authentic Windows acrylic frosted glass with live background blur',
                isTransparent,
                setIsTransparent
              )}
            </div>

            {/* Background Transparency Opacity Slider */}
            <div className="space-y-3 max-w-xl">
              <div className="flex justify-between items-center">
                <span className="text-[14px] font-medium text-neutral-100">
                  Background transparency
                </span>
                <span className="text-[12px] text-neutral-400 font-mono">
                  {transparencyOpacity}%
                </span>
              </div>
              <div className="relative flex items-center">
                <input
                  type="range"
                  min="20"
                  max="100"
                  value={transparencyOpacity}
                  disabled={!isTransparent}
                  onChange={(e) => setTransparencyOpacity(Number(e.target.value))}
                  className="w-full h-1.5 bg-neutral-700 rounded-lg appearance-none cursor-pointer accent-[#d41b6c] disabled:opacity-40"
                  style={{
                    accentColor: currentTheme.accent,
                  }}
                />
              </div>
            </div>

            {/* Color Themes Section (win_032) */}
            <div className="space-y-4 pt-4">
              <h2 className="text-[16px] font-medium text-white">Color themes</h2>

              <div className="flex flex-wrap gap-4 items-start">
                {(Object.keys(COLOR_THEMES) as ThemeId[]).map((id) => {
                  const t = COLOR_THEMES[id];
                  const isSelected = themeId === id;

                  return (
                    <button
                      key={id}
                      onClick={() => setTheme(id)}
                      className={`flex flex-col items-center gap-2 p-2.5 rounded-lg transition-all focus:outline-none ${
                        isSelected
                          ? 'ring-2 bg-white/10 shadow-lg'
                          : 'hover:bg-white/5 opacity-90 hover:opacity-100'
                      }`}
                      style={{
                        borderColor: isSelected ? t.accent : 'transparent',
                        outlineColor: isSelected ? t.accent : 'transparent',
                      }}
                    >
                      {/* Theme Dual-Swatch Box (matching win_032 / win_033) */}
                      <div
                        className="w-14 h-14 rounded-md flex items-center justify-center relative shadow-md transition-transform active:scale-95"
                        style={{ backgroundColor: t.swatchOuter }}
                      >
                        <div
                          className="w-7 h-7 rounded-sm shadow-inner flex items-center justify-center"
                          style={{ backgroundColor: t.swatchInner }}
                        >
                          {isSelected && (
                            <Check
                              size={14}
                              className={t.isLight ? 'text-black' : 'text-white'}
                            />
                          )}
                        </div>
                      </div>

                      {/* Theme Name */}
                      <span
                        className={`text-[12px] ${
                          isSelected ? 'font-semibold text-white' : 'text-neutral-300'
                        }`}
                      >
                        {t.name}
                      </span>
                    </button>
                  );
                })}

                {/* Add Theme Tile */}
                <button
                  type="button"
                  onClick={() => alert('Custom theme creator will be enabled in the upcoming release!')}
                  className="flex flex-col items-center gap-2 p-2.5 rounded-lg opacity-60 hover:opacity-100 transition-opacity"
                  title="Custom accent themes"
                >
                  <div className="w-14 h-14 rounded-md border-2 border-dashed border-neutral-500 flex items-center justify-center hover:border-neutral-300">
                    <Plus size={20} className="text-neutral-400" />
                  </div>
                  <span className="text-[12px] text-neutral-400">Add theme</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* 5. BACKUP & RESTORE (win_042)                                */}
        {/* ============================================================ */}
        {activeCategory === 'backup' && (
          <div className="space-y-6 max-w-3xl pb-16">
            <div className="flex items-baseline gap-2">
              <h1 className="text-[22px] font-semibold text-white tracking-tight">
                Backup & Restore
              </h1>
              <span className="text-[12px] text-neutral-400 font-normal">
                Deprecated
              </span>
            </div>

            {/* Choose operation */}
            <div className="space-y-2">
              <h2 className="text-[15px] font-medium text-neutral-200">
                Choose operation
              </h2>
              <p className="text-[12px] text-neutral-400">
                Select the operation you want to perform
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                {/* Backup Radio Card */}
                <label
                  className={`p-4 rounded-lg border cursor-pointer transition-all ${
                    backupOperation === 'backup'
                      ? 'bg-white/10 border-white/20'
                      : 'bg-black/20 border-white/5 hover:border-white/10'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className="w-4 h-4 rounded-full border flex items-center justify-center"
                      style={{
                        borderColor: backupOperation === 'backup' ? currentTheme.accent : '#666',
                      }}
                    >
                      {backupOperation === 'backup' && (
                        <div
                          className="w-2 h-2 rounded-full"
                          style={{ backgroundColor: currentTheme.accent }}
                        />
                      )}
                    </div>
                    <span className="text-[14px] font-medium text-white">Backup</span>
                  </div>
                  <p className="text-[12px] text-neutral-400 mt-2 pl-7">
                    Create a backup copy with the selected configurations.
                  </p>
                  <input
                    type="radio"
                    name="operation"
                    value="backup"
                    checked={backupOperation === 'backup'}
                    onChange={() => setBackupOperation('backup')}
                    className="sr-only"
                  />
                </label>

                {/* Restore Radio Card */}
                <label
                  className={`p-4 rounded-lg border cursor-pointer transition-all ${
                    backupOperation === 'restore'
                      ? 'bg-white/10 border-white/20'
                      : 'bg-black/20 border-white/5 hover:border-white/10'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className="w-4 h-4 rounded-full border flex items-center justify-center"
                      style={{
                        borderColor: backupOperation === 'restore' ? currentTheme.accent : '#666',
                      }}
                    >
                      {backupOperation === 'restore' && (
                        <div
                          className="w-2 h-2 rounded-full"
                          style={{ backgroundColor: currentTheme.accent }}
                        />
                      )}
                    </div>
                    <span className="text-[14px] font-medium text-white">Restore</span>
                  </div>
                  <p className="text-[12px] text-neutral-400 mt-2 pl-7 leading-relaxed">
                    Restore the selected configurations from the backup file.
                    <br />
                    <span className="text-neutral-500">
                      Note: This will override current configurations, e.g. new notes, highlights etc can be lost if they are not contained in the backup copy.
                    </span>
                  </p>
                  <input
                    type="radio"
                    name="operation"
                    value="restore"
                    checked={backupOperation === 'restore'}
                    onChange={() => setBackupOperation('restore')}
                    className="sr-only"
                  />
                </label>
              </div>
            </div>

            {/* Choose configuration checkboxes */}
            <div className="space-y-3 pt-2">
              <h2 className="text-[15px] font-medium text-neutral-200">
                Choose configuration
              </h2>
              <p className="text-[12px] text-neutral-400">
                Select the configuration for backup or restore operation
              </p>

              <div className="flex flex-wrap gap-6 pt-2">
                {[
                  { key: 'bookFiles', label: 'Book files' },
                  { key: 'metadata', label: 'Book metadata' },
                  { key: 'notesHighlights', label: 'Notes & highlights' },
                  { key: 'bookmarks', label: 'Bookmarks' },
                  { key: 'favorites', label: 'Book favorite list' },
                ].map((item) => {
                  const isChecked = (backupConfigs as any)[item.key];
                  return (
                    <label
                      key={item.key}
                      className="flex items-center gap-2 cursor-pointer select-none"
                    >
                      <button
                        type="button"
                        onClick={() =>
                          setBackupConfigs((prev) => ({
                            ...prev,
                            [item.key]: !isChecked,
                          }))
                        }
                        className="w-4 h-4 rounded flex items-center justify-center transition-colors"
                        style={{
                          backgroundColor: isChecked ? currentTheme.accent : '#333336',
                        }}
                      >
                        {isChecked && <Check size={12} className="text-white" />}
                      </button>
                      <span className="text-[13px] text-neutral-200">{item.label}</span>
                    </label>
                  );
                })}
              </div>
            </div>

            {/* Choose storage */}
            <div className="space-y-2 pt-2">
              <h2 className="text-[15px] font-medium text-neutral-200">
                Choose storage
              </h2>
              <p className="text-[12px] text-neutral-400">
                Select the source or target storage for the operation
              </p>

              <div className="flex items-center gap-3 pt-1">
                <button
                  type="button"
                  onClick={() => {
                    const custom = prompt('Enter backup folder path:', backupStoragePath);
                    if (custom) setBackupStoragePath(custom);
                  }}
                  className="px-4 py-1.5 rounded bg-neutral-800 hover:bg-neutral-700 text-white text-[13px] border border-white/10 transition-colors"
                >
                  Select folder
                </button>
                <span className="text-[12px] text-neutral-400 font-mono">
                  {backupStoragePath}
                </span>
              </div>
            </div>

            {/* Action Button */}
            <div className="pt-2">
              <button
                type="button"
                onClick={handleExecuteBackupRestore}
                disabled={isBackupRunning}
                className="px-8 py-2 rounded text-[13px] font-medium text-white transition-all disabled:opacity-50"
                style={{ backgroundColor: currentTheme.accent }}
              >
                {isBackupRunning ? 'Processing...' : backupOperation === 'backup' ? 'Backup' : 'Restore'}
              </button>
            </div>

            {/* Logs console */}
            <div className="space-y-2 pt-4">
              <div className="flex justify-between items-center">
                <span className="text-[13px] font-medium text-neutral-300">Logs</span>
                <button
                  type="button"
                  onClick={() => setBackupLogs(['Console cleared.'])}
                  className="text-[11px] text-neutral-400 hover:text-white transition-colors"
                >
                  Clear log
                </button>
              </div>
              <div className="w-full h-32 rounded-lg bg-black/40 border border-white/10 p-3 font-mono text-[12px] text-neutral-300 overflow-y-auto space-y-1">
                {backupLogs.map((log, i) => (
                  <div key={i} className="leading-tight">{log}</div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* 6. CLOUD SYNC (win_043)                                      */}
        {/* ============================================================ */}
        {activeCategory === 'cloud-sync' && (
          <div className="space-y-6 max-w-3xl pb-16">
            <div className="flex items-baseline gap-2">
              <h1 className="text-[22px] font-semibold text-white tracking-tight">
                Cloud sync
              </h1>
              <span className="text-[12px] text-neutral-400 font-normal">
                Beta
              </span>
            </div>

            {/* Google Drive Account Card */}
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => {
                  const nextState = !isGoogleLinked;
                  setIsGoogleLinked(nextState);
                  updateSetting('aquile_cloud_linked', nextState);
                  if (nextState) {
                    setCloudSyncStatus('Linked as alex.reader@gmail.com');
                  } else {
                    setCloudSyncStatus(null);
                  }
                }}
                className="px-4 py-2 rounded-md bg-neutral-800 hover:bg-neutral-700 text-white text-[13px] font-medium flex items-center gap-2 border border-white/10 transition-colors"
              >
                {/* Google G icon */}
                <svg className="w-4 h-4" viewBox="0 0 24 24">
                  <path
                    fill="#4285F4"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                  />
                </svg>
                <span>{isGoogleLinked ? 'Unlink Google account' : 'Link Google account'}</span>
              </button>

              <button
                type="button"
                onClick={() => alert('Google Drive Cloud Sync uses encrypted app-data storage to keep your book progress synchronized seamlessly across your Linux and Android installations.')}
                className="w-8 h-8 rounded-md bg-neutral-800 hover:bg-neutral-700 text-neutral-300 hover:text-white flex items-center justify-center border border-white/10 transition-colors"
                title="Help"
              >
                <span className="text-[14px]">?</span>
              </button>
            </div>

            {isGoogleLinked && (
              <div className="text-[12px] text-emerald-400 font-medium flex items-center gap-1.5">
                <Check size={14} />
                <span>Linked as alex.reader@gmail.com</span>
              </div>
            )}

            <div>
              <a
                href="#learn"
                onClick={(e) => {
                  e.preventDefault();
                  alert('Cloud Sync uses your personal Google Drive storage space. Books are uploaded in an isolated app-folder.');
                }}
                className="text-[13px] hover:underline"
                style={{ color: currentTheme.accent }}
              >
                Tap to learn more about how cloud sync works or if you are facing issues with cloud sync.
              </a>
            </div>

            <div className="space-y-1 divide-y divide-white/5 pt-2">
              {renderToggle(
                'Enable cloud sync',
                'Toggle cross-device sync of books and metadata using the linked Google drive account.',
                enableCloudSync,
                (val) => {
                  setEnableCloudSync(val);
                  updateSetting('aquile_cloud_enabled', val);
                }
              )}

              {renderToggle(
                'Use alternate sign-in method',
                'If facing issues with Google account sign-in, then try out alternate way.',
                useAltSignIn,
                (val) => {
                  setUseAltSignIn(val);
                  updateSetting('aquile_cloud_alt_signin', val);
                }
              )}
            </div>

            {/* Sync mode selector */}
            <div className="space-y-3 pt-2">
              <h2 className="text-[14px] font-medium text-neutral-200">Sync mode</h2>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="syncmode"
                    value="all"
                    checked={syncMode === 'all'}
                    onChange={() => {
                      setSyncMode('all');
                      updateSetting('aquile_cloud_mode', 'all');
                    }}
                    className="accent-[#d41b6c]"
                    style={{ accentColor: currentTheme.accent }}
                  />
                  <span className="text-[13px] text-neutral-200">All books</span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="syncmode"
                    value="selected"
                    checked={syncMode === 'selected'}
                    onChange={() => {
                      setSyncMode('selected');
                      updateSetting('aquile_cloud_mode', 'selected');
                    }}
                    className="accent-[#d41b6c]"
                    style={{ accentColor: currentTheme.accent }}
                  />
                  <span className="text-[13px] text-neutral-200">Selected books</span>
                </label>
              </div>
            </div>

            {/* Descriptive paragraphs matching win_043 */}
            <div className="pt-4 space-y-4 text-[13px] text-neutral-300 leading-relaxed border-t border-white/5">
              <p>
                Cloud sync uses Google Drive to enable cross device sync (Android and Windows) of books, book files, metadata, reading position and annotations.
              </p>
              <p>
                On app start, latest state of 'synced' books are downloaded from cloud. Books are uploaded/synced to cloud when opened for reading. Once the book is closed, latest state is uploaded again to the cloud.
              </p>
              <p>
                Options are provided to control the sync behaviour. With 'All books' option, by default all the books are synced, unless user has excluded some books from sync. 'Selected books' means only user selected books are synced. Books can be included/excluded by using the book context menu.
              </p>
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* 7. READING INSIGHTS (EMBEDDED IN SETTINGS) (win_044)        */}
        {/* ============================================================ */}
        {activeCategory === 'insights' && (
          <InsightsView isEmbedded={true} />
        )}

        {/* ============================================================ */}
        {/* 8. FAQ (win_052)                                             */}
        {/* ============================================================ */}
        {activeCategory === 'faq' && (
          <div className="space-y-6 max-w-3xl pb-16">
            <h1 className="text-[22px] font-semibold text-white tracking-tight">
              Frequently Asked Questions
            </h1>

            <div className="space-y-3">
              {[
                {
                  id: 0,
                  q: 'How does Cloud Sync work across devices?',
                  a: 'Cloud Sync securely connects to your Google Drive to sync books, reading positions, bookmarks, notes, and highlights between your Linux desktop and other supported platforms. All data is kept private in your personal cloud storage.',
                },
                {
                  id: 1,
                  q: 'What book formats does Aquile Reader support?',
                  a: 'Aquile Reader supports EPUB (.epub), PDF (.pdf), Comic Book Archives (.cbz, .cbr), and MOBI files. Modern EPUB rendering is powered by our native Rust layout engine.',
                },
                {
                  id: 2,
                  q: 'How do I add books to my library?',
                  a: 'You can add books by clicking the "+ Add Book" button in the library, dragging and dropping files directly into the window, configuring automatic "Sync Folders", or downloading free classics via the OPDS Catalogs browser.',
                },
                {
                  id: 3,
                  q: 'Can I customize fonts and reading themes?',
                  a: 'Yes! While reading, open the reader controls to change fonts, font size, line spacing, margins, and page colors (light, sepia, dark, and custom themes). You can also toggle "Use book\'s fonts" under Reader settings.',
                },
                {
                  id: 4,
                  q: 'How do annotations and highlights work?',
                  a: 'Simply select text while reading to create highlights in various colors, add personal notes, or copy quotes. All annotations are accessible from the Annotations hub and can be exported as text or JSON.',
                },
                {
                  id: 5,
                  q: 'Is my data stored locally or uploaded to external servers?',
                  a: 'All books, reading statistics, and settings are stored 100% locally on your machine. No telemetry or book data is ever uploaded unless you explicitly enable Google Drive Cloud Sync.',
                },
              ].map((item) => {
                const isOpen = expandedFaqId === item.id;
                return (
                  <div
                    key={item.id}
                    className="border border-white/10 rounded-lg bg-black/20 overflow-hidden"
                  >
                    <button
                      type="button"
                      onClick={() => setExpandedFaqId(isOpen ? null : item.id)}
                      className="w-full px-5 py-4 flex items-center justify-between text-left hover:bg-white/5 transition-colors"
                    >
                      <span className="text-[14px] font-medium text-white">{item.q}</span>
                      <ChevronDown
                        size={16}
                        className={`text-neutral-400 transition-transform ${
                          isOpen ? 'rotate-180' : ''
                        }`}
                      />
                    </button>
                    {isOpen && (
                      <div className="px-5 pb-4 pt-1 text-[13px] text-neutral-300 leading-relaxed border-t border-white/5">
                        {item.a}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* 9. CHANGE LOG (win_050)                                      */}
        {/* ============================================================ */}
        {activeCategory === 'changelog' && (
          <div className="space-y-6 max-w-3xl pb-16">
            <h1 className="text-[22px] font-semibold text-white tracking-tight">
              Change log
            </h1>

            <div className="space-y-6">
              {/* v 1.1.67 */}
              <div className="space-y-2">
                <h3
                  className="text-[15px] font-semibold"
                  style={{ color: currentTheme.accent }}
                >
                  v 1.1.67
                </h3>
                <ul className="space-y-1 text-[13px] text-neutral-300 list-disc list-inside leading-relaxed">
                  <li>New optional Modern EPUB rendering engine under Settings → Reader → Experimental</li>
                  <li>New adjustable EPUB reading width and page margins when using the Modern EPUB rendering engine</li>
                  <li>Fix for images not displaying correctly in some PDF files</li>
                  <li>Fix for default dictionaries</li>
                  <li>Collections renamed to Annotations for clearer management of highlights, notes, and bookmarks</li>
                  <li>App supports 10 new languages now - German, Spanish, Finnish, French, Korean, Polish, Russian, Slovenian, Swedish, Turkish</li>
                  <li>Other improvements and stability fixes</li>
                </ul>
              </div>

              {/* v 1.1.65 */}
              <div className="space-y-2">
                <h3
                  className="text-[15px] font-semibold"
                  style={{ color: currentTheme.accent }}
                >
                  v 1.1.65
                </h3>
                <ul className="space-y-1 text-[13px] text-neutral-300 list-disc list-inside leading-relaxed">
                  <li>New customizable reading footer for books</li>
                  <li>Whole-book page numbering support for EPUB</li>
                  <li>Support for Reading Insights for PDF/Comic files</li>
                  <li>Jump directly to a specific EPUB page</li>
                </ul>
              </div>

              {/* v 1.1.64 */}
              <div className="space-y-2">
                <h3
                  className="text-[15px] font-semibold"
                  style={{ color: currentTheme.accent }}
                >
                  v 1.1.64
                </h3>
                <ul className="space-y-1 text-[13px] text-neutral-300 list-disc list-inside leading-relaxed">
                  <li>Support for Comic books (cbz, cbr)</li>
                </ul>
              </div>

              {/* v 1.1.62 */}
              <div className="space-y-2">
                <h3
                  className="text-[15px] font-semibold"
                  style={{ color: currentTheme.accent }}
                >
                  v 1.1.62
                </h3>
                <ul className="space-y-1 text-[13px] text-neutral-300 list-disc list-inside leading-relaxed">
                  <li>Fix for Dictionary in all languages</li>
                </ul>
              </div>

              {/* v 1.1.61 */}
              <div className="space-y-2">
                <h3
                  className="text-[15px] font-semibold"
                  style={{ color: currentTheme.accent }}
                >
                  v 1.1.61
                </h3>
                <ul className="space-y-1 text-[13px] text-neutral-300 list-disc list-inside leading-relaxed">
                  <li>Support for annotations (Highlight and Notes) in PDF file types</li>
                </ul>
              </div>

              {/* v 1.1.57 */}
              <div className="space-y-2">
                <h3
                  className="text-[15px] font-semibold"
                  style={{ color: currentTheme.accent }}
                >
                  v 1.1.57
                </h3>
                <ul className="space-y-1 text-[13px] text-neutral-300 list-disc list-inside leading-relaxed">
                  <li>Support for text search in PDF files</li>
                  <li>Reader Theme support for PDF files with color inversion</li>
                  <li>Fix for last book read position not being loaded correctly</li>
                  <li>Other improvements and stability fixes</li>
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* 10. ABOUT US (win_051)                                       */}
        {/* ============================================================ */}
        {activeCategory === 'about' && (
          <div className="h-full flex flex-col items-center justify-center -mt-8 space-y-6">
            {/* 3D Aquile Reader Icon matching win_051 */}
            <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-[#3b9be8] to-[#1268b8] shadow-2xl flex items-center justify-center relative p-3 border border-white/20">
              <div className="w-full h-full flex flex-col items-center justify-center relative">
                {/* White bookmark ribbon with 'A' */}
                <div className="w-7 h-11 bg-white rounded-b-sm shadow-md flex items-start justify-center pt-1">
                  <span className="text-[14px] font-bold text-[#1268b8] font-sans">A</span>
                </div>
                <div className="w-14 h-1 bg-white/40 rounded-full mt-2" />
                <div className="w-10 h-1 bg-white/30 rounded-full mt-1" />
              </div>
            </div>

            {/* Version & Copyright */}
            <div className="text-center space-y-1">
              <div className="text-[14px] font-medium text-white">v 1.1.67</div>
              <div className="text-[12px] text-neutral-400">
                © Optimilia Studios. All Rights Reserved.
              </div>
            </div>

            {/* Social & Action icons matching win_051 */}
            <div className="flex items-center gap-6 pt-4">
              {/* Group 1: Reddit, X, Substack */}
              <div className="flex items-center gap-4">
                <a
                  href="https://reddit.com/r/AquileReader"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-10 h-10 rounded-lg bg-[#ff4500] hover:scale-105 flex items-center justify-center transition-all shadow-md"
                  title="Reddit Community"
                >
                  <span className="text-[16px] font-bold text-white">r/</span>
                </a>

                <a
                  href="https://twitter.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-10 h-10 rounded-lg bg-black border border-white/20 hover:scale-105 flex items-center justify-center transition-all shadow-md"
                  title="X (Twitter)"
                >
                  <span className="text-[16px] font-bold text-white font-sans">𝕏</span>
                </a>

                <a
                  href="https://substack.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-10 h-10 rounded-lg bg-[#2b2b2e] hover:scale-105 flex items-center justify-center transition-all shadow-md text-cyan-400"
                  title="Newsletter"
                >
                  <FileText size={18} />
                </a>
              </div>

              {/* Vertical divider */}
              <div className="h-8 w-px bg-white/10" />

              {/* Group 2: Support & Rate */}
              <div className="flex items-center gap-4">
                <button
                  type="button"
                  onClick={() => alert('Support portal: support@optimilia.com')}
                  className="w-10 h-10 rounded-lg bg-[#2b2b2e] hover:scale-105 flex items-center justify-center transition-all shadow-md text-amber-400"
                  title="Contact Support"
                >
                  <MessageSquare size={18} />
                </button>

                <button
                  type="button"
                  onClick={() => alert('Thank you for using Aquile Reader on Linux!')}
                  className="w-10 h-10 rounded-lg bg-[#2b2b2e] hover:scale-105 flex items-center justify-center transition-all shadow-md text-yellow-400"
                  title="Rate & Review"
                >
                  <Star size={18} />
                </button>
              </div>

              {/* Vertical divider */}
              <div className="h-8 w-px bg-white/10" />

              {/* Group 3: Privacy & Terms */}
              <div className="flex items-center gap-4">
                <button
                  type="button"
                  onClick={() => alert('Privacy Policy: All books, notes, and reading statistics remain strictly on your local machine. No tracking or telemetry.')}
                  className="w-10 h-10 rounded-lg bg-[#2b2b2e] hover:scale-105 flex items-center justify-center transition-all shadow-md text-cyan-400"
                  title="Privacy Policy"
                >
                  <Shield size={18} />
                </button>

                <button
                  type="button"
                  onClick={() => alert('Terms of Service: Free and open public domain reading software with no advertisements.')}
                  className="w-10 h-10 rounded-lg bg-[#2b2b2e] hover:scale-105 flex items-center justify-center transition-all shadow-md text-blue-400"
                  title="Terms of Service"
                >
                  <Info size={18} />
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default SettingsView;
