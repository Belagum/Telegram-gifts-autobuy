// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import type { ReactNode } from "react";
import React from "react";
import { NavLink } from "react-router-dom";
import { useTheme } from "../../lib/theme/useTheme";
import { logout } from "../../../features/auth/api";
import { showError, showSuccess } from "../feedback/toast";
import { useUiStore } from "../../../app/store/uiStore";
import { Footer } from "../footer/Footer";
import "./layout.css";

export interface AppLayoutProps {
  children: ReactNode;
}

// SVG иконки
const HomeIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    <polyline points="9 22 9 12 15 12 15 22" />
  </svg>
);

const GiftIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="20 12 20 22 4 22 4 12" />
    <rect x="2" y="7" width="20" height="5" />
    <line x1="12" y1="22" x2="12" y2="7" />
    <path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z" />
    <path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z" />
  </svg>
);

const SettingsIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="3" />
    <path d="M12 1v6m0 6v6m-9-9h6m6 0h6M4.22 4.22l4.24 4.24m7.07 7.07l4.24 4.24M4.22 19.78l4.24-4.24m7.07-7.07l4.24-4.24" />
  </svg>
);

const SunIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="5" />
    <line x1="12" y1="1" x2="12" y2="3" />
    <line x1="12" y1="21" x2="12" y2="23" />
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
    <line x1="1" y1="12" x2="3" y2="12" />
    <line x1="21" y1="12" x2="23" y2="12" />
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
  </svg>
);

const MoonIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
  </svg>
);

const LogoutIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <polyline points="16 17 21 12 16 7" />
    <line x1="21" y1="12" x2="9" y2="12" />
  </svg>
);

const MenuIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="3" y1="12" x2="21" y2="12" />
    <line x1="3" y1="6" x2="21" y2="6" />
    <line x1="3" y1="18" x2="21" y2="18" />
  </svg>
);

const ChevronLeftIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="15 18 9 12 15 6" />
  </svg>
);

const ChevronRightIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="9 18 15 12 9 6" />
  </svg>
);

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const { theme, toggleTheme } = useTheme();
  const collapsed = useUiStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);

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
      <aside className={`layout__sidebar ${collapsed ? "layout__sidebar--collapsed" : ""}`}>
        <div className="layout__logo">
          {collapsed ? (
            <button className="layout__toggle-btn" onClick={toggleSidebar} title="Развернуть">
              <ChevronRightIcon />
            </button>
          ) : (
            <>
              <span>GiftBuyer</span>
              <button className="layout__toggle-btn" onClick={toggleSidebar} title="Свернуть">
                <ChevronLeftIcon />
              </button>
            </>
          )}
        </div>
        <nav className="layout__nav">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "is-active" : "")} title="Главная">
            <HomeIcon />
            {!collapsed && <span>Главная</span>}
          </NavLink>
          <NavLink to="/gifts" className={({ isActive }) => (isActive ? "is-active" : "")} title="Подарки">
            <GiftIcon />
            {!collapsed && <span>Подарки</span>}
          </NavLink>
          <NavLink to="/settings" className={({ isActive }) => (isActive ? "is-active" : "")} title="Настройки">
            <SettingsIcon />
            {!collapsed && <span>Настройки</span>}
          </NavLink>
        </nav>
        <div className="layout__sidebar-footer">
          {collapsed ? (
            <>
              <button className="layout__icon-btn" onClick={toggleTheme} title={theme === "light" ? "Светлая тема" : "Тёмная тема"}>
                {theme === "light" ? <SunIcon /> : <MoonIcon />}
              </button>
              <button className="layout__icon-btn" onClick={handleLogout} title="Выйти">
                <LogoutIcon />
              </button>
            </>
          ) : (
            <>
              <button className="layout__footer-btn layout__footer-btn--secondary" onClick={toggleTheme}>
                {theme === "light" ? <SunIcon /> : <MoonIcon />}
                <span>Тема: {theme === "light" ? "Светлая" : "Тёмная"}</span>
              </button>
              <button className="layout__footer-btn layout__footer-btn--ghost" onClick={handleLogout}>
                <LogoutIcon />
                <span>Выйти</span>
              </button>
            </>
          )}
        </div>
      </aside>
      <div className="layout__main">
        <main className="layout__content">{children}</main>
        <Footer />
      </div>
    </div>
  );
};
