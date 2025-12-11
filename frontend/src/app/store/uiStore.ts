// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import { create } from "zustand";

export type ThemeName = "light" | "dark";

interface UiState {
  theme: ThemeName;
  setTheme: (theme: ThemeName) => void;
  toggleTheme: () => void;
  globalLoading: boolean;
  setGlobalLoading: (value: boolean) => void;
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (value: boolean) => void;
  toggleSidebar: () => void;
}

const safeGetItem = (key: string): string | null => {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
};

const safeSetItem = (key: string, value: string): void => {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(key, value);
  } catch {
  }
};

const detectInitialTheme = (): ThemeName => {
  if (typeof window === "undefined") {
    return "light";
  }
  const saved = safeGetItem("ui.theme");
  if (saved === "light" || saved === "dark") {
    return saved;
  }
  const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  return prefersDark ? "dark" : "light";
};

export const useUiStore = create<UiState>((set, get) => ({
  theme: detectInitialTheme(),
  setTheme: (theme) => {
    set({ theme });
    safeSetItem("ui.theme", theme);
    if (typeof document !== "undefined") {
      const root = document.documentElement;
      root.classList.add("theme-transition");
      requestAnimationFrame(() => {
        root.setAttribute("data-theme", theme);
        window.setTimeout(() => {
          root.classList.remove("theme-transition");
        }, 300);
      });
    }
  },
  toggleTheme: () => {
    const next = get().theme === "light" ? "dark" : "light";
    get().setTheme(next);
  },
  globalLoading: false,
  setGlobalLoading: (value) => set({ globalLoading: value }),
  sidebarCollapsed: safeGetItem("ui.sidebarCollapsed") === "true",
  setSidebarCollapsed: (value) => {
    set({ sidebarCollapsed: value });
    safeSetItem("ui.sidebarCollapsed", String(value));
  },
  toggleSidebar: () => {
    const next = !get().sidebarCollapsed;
    get().setSidebarCollapsed(next);
  },
}));

export const initializeThemeDom = () => {
  if (typeof document === "undefined") {
    return;
  }
  const storeTheme = useUiStore.getState().theme;
  document.documentElement.setAttribute("data-theme", storeTheme);
};
