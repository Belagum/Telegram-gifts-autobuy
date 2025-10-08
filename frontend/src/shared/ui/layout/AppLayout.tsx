// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import type { ReactNode } from "react";
import React from "react";
import { NavLink } from "react-router-dom";
import { Button } from "../button/Button";
import { useTheme } from "../../lib/theme/useTheme";
import { logout } from "../../../features/auth/api";
import { showError, showSuccess } from "../feedback/toast";
import "./layout.css";

export interface AppLayoutProps {
  children: ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const { theme, toggleTheme } = useTheme();

  const handleLogout = async () => {
    try {
      await logout();
      showSuccess("Вы вышли из системы");
      window.location.href = "/login";
    } catch (error) {
      showError(error);
    }
  };

  return (
    <div className="layout">
      <aside className="layout__sidebar">
        <div className="layout__logo">GiftBuyer</div>
        <nav className="layout__nav">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "is-active" : "")}>Главная</NavLink>
          <NavLink to="/gifts" className={({ isActive }) => (isActive ? "is-active" : "")}>Подарки</NavLink>
          <NavLink to="/settings" className={({ isActive }) => (isActive ? "is-active" : "")}>Настройки</NavLink>
        </nav>
        <div className="layout__sidebar-footer">
          <Button variant="secondary" onClick={toggleTheme}>
            Тема: {theme === "light" ? "Светлая" : "Тёмная"}
          </Button>
          <Button variant="ghost" onClick={handleLogout}>
            Выйти
          </Button>
        </div>
      </aside>
      <main className="layout__content">{children}</main>
    </div>
  );
};
