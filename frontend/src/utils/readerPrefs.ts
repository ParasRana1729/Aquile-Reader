export type PageTransitionStyle = 'None' | 'Slide' | 'Fade' | 'Flip';

const PAGE_TRANSITION_KEY = 'aquile_setting_page_transition';
const PAGE_TRANSITION_EVENT = 'aquile:page-transition';

const VALID_STYLES: PageTransitionStyle[] = ['None', 'Slide', 'Fade', 'Flip'];

export function getPageTransition(): PageTransitionStyle {
  try {
    const raw = localStorage.getItem(PAGE_TRANSITION_KEY);
    if (raw && (VALID_STYLES as string[]).includes(raw)) {
      return raw as PageTransitionStyle;
    }
  } catch {
    // ignore storage failures (private mode, etc.)
  }
  return 'None';
}

export function setPageTransition(style: PageTransitionStyle): void {
  try {
    localStorage.setItem(PAGE_TRANSITION_KEY, style);
  } catch {
    // ignore storage failures
  }
  window.dispatchEvent(new CustomEvent<PageTransitionStyle>(PAGE_TRANSITION_EVENT, { detail: style }));
}

export function subscribePageTransition(listener: (style: PageTransitionStyle) => void): () => void {
  const handler = (event: Event) => {
    listener((event as CustomEvent<PageTransitionStyle>).detail ?? getPageTransition());
  };
  window.addEventListener(PAGE_TRANSITION_EVENT, handler);
  return () => window.removeEventListener(PAGE_TRANSITION_EVENT, handler);
}
