// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import { useCallback } from "react";
import { useUiStore, ThemeName } from "../../../app/store/uiStore";

export const useTheme = () => {
  const theme = useUiStore((state) => state.theme);
  const setTheme = useUiStore((state) => state.setTheme);
  const toggleThemeStore = useUiStore((state) => state.toggleTheme);

  const toggleTheme = useCallback(() => {
    toggleThemeStore();
  }, [toggleThemeStore]);

  const changeTheme = useCallback(
    (name: ThemeName) => {
      setTheme(name);
    },
    [setTheme],
  );

  return { theme, setTheme: changeTheme, toggleTheme };
};
