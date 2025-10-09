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
}

const detectInitialTheme = (): ThemeName => {
  if (typeof window === "undefined") {
    return "light";
  }
  const saved = window.localStorage.getItem("ui.theme") as ThemeName | null;
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
    if (typeof window !== "undefined") {
      window.localStorage.setItem("ui.theme", theme);
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
}));

export const initializeThemeDom = () => {
  if (typeof document === "undefined") {
    return;
  }
  const storeTheme = useUiStore.getState().theme;
  document.documentElement.setAttribute("data-theme", storeTheme);
};
