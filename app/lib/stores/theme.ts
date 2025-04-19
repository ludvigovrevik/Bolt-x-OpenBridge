import { atom } from 'nanostores';

export type Theme = 'dark' | 'light';

export const kTheme = 'bolt_theme';

export function themeIsDark() {
  return themeStore.get() === 'dark';
}

export const DEFAULT_THEME = 'light';

export const themeStore = atom<Theme>(DEFAULT_THEME); // Initialize with default first

function initStoreClient() {
  // This function runs only on the client after initial render
  const persistedTheme = localStorage.getItem(kTheme) as Theme | undefined;
  // Read the theme set by the inline script in root.tsx
  const themeAttribute = document.querySelector('html')?.getAttribute('data-theme') as Theme | undefined;

  // Prioritize localStorage, then the html attribute, then default
  const initialTheme = persistedTheme ?? themeAttribute ?? DEFAULT_THEME;
  themeStore.set(initialTheme); // Update the store state
}

// Run the client-side initialization logic after the initial render
if (!import.meta.env.SSR) {
  // Use requestAnimationFrame to ensure it runs after the initial paint
  // and the inline script in root.tsx has definitely run.
  requestAnimationFrame(initStoreClient);
}

export function toggleTheme() {
  const currentTheme = themeStore.get();
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

  themeStore.set(newTheme);
  localStorage.setItem(kTheme, newTheme);
  document.querySelector('html')?.setAttribute('data-theme', newTheme);
}
