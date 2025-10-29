// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { AdminDashboard } from "../../features/admin/AdminDashboard";
import { AuditLogsViewer } from "../../features/admin/AuditLogsViewer";
import { ErrorStatsPanel } from "../../features/admin/ErrorStatsPanel";
import { SuspiciousActivityPanel } from "../../features/admin/SuspiciousActivityPanel";
import { UserAuditPanel } from "../../features/admin/UserAuditPanel";
import { UsersManagement } from "../../features/admin/UsersManagement";
import "../../features/admin/admin.css";
import "./admin.css";

type AdminSection =
  | "dashboard"
  | "audit-logs"
  | "user-audit"
  | "suspicious"
  | "errors"
  | "users";

export const AdminPage: React.FC = () => {
  const [activeSection, setActiveSection] =
    React.useState<AdminSection>("dashboard");

  const renderSection = () => {
    switch (activeSection) {
      case "dashboard":
        return <AdminDashboard />;
      case "audit-logs":
        return <AuditLogsViewer />;
      case "user-audit":
        return <UserAuditPanel />;
      case "suspicious":
        return <SuspiciousActivityPanel />;
      case "errors":
        return <ErrorStatsPanel />;
      case "users":
        return <UsersManagement />;
      default:
        return <AdminDashboard />;
    }
  };

  return (
    <div className="admin-page">
      <header className="admin-page__header">
        <h1>Панель администратора</h1>
      </header>

      <div className="admin-page__layout">
        <nav className="admin-page__nav">
          <button
            className={
              activeSection === "dashboard" ? "nav-item nav-item--active" : "nav-item"
            }
            onClick={() => setActiveSection("dashboard")}
          >
            📊 Дашборд
          </button>
          <button
            className={
              activeSection === "audit-logs" ? "nav-item nav-item--active" : "nav-item"
            }
            onClick={() => setActiveSection("audit-logs")}
          >
            📋 Журнал аудита
          </button>
          <button
            className={
              activeSection === "user-audit" ? "nav-item nav-item--active" : "nav-item"
            }
            onClick={() => setActiveSection("user-audit")}
          >
            🔍 Логи пользователя
          </button>
          <button
            className={
              activeSection === "suspicious" ? "nav-item nav-item--active" : "nav-item"
            }
            onClick={() => setActiveSection("suspicious")}
          >
            ⚠️ Подозрительная активность
          </button>
          <button
            className={
              activeSection === "errors" ? "nav-item nav-item--active" : "nav-item"
            }
            onClick={() => setActiveSection("errors")}
          >
            ❌ Статистика ошибок
          </button>
          <button
            className={
              activeSection === "users" ? "nav-item nav-item--active" : "nav-item"
            }
            onClick={() => setActiveSection("users")}
          >
            👥 Пользователи
          </button>
        </nav>

        <main className="admin-page__content">{renderSection()}</main>
      </div>
    </div>
  );
};

