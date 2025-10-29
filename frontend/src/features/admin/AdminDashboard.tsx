// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { getDashboardStats } from "../../entities/admin/api";
import type { DashboardStats } from "../../entities/admin/model";
import { showError } from "../../shared/ui/feedback/toast";

export const AdminDashboard: React.FC = () => {
  const [stats, setStats] = React.useState<DashboardStats | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        setLoading(true);
        const data = await getDashboardStats();
        if (!cancelled) {
          setStats(data);
        }
      } catch (error) {
        if (!cancelled) {
          showError(error, "Не удалось загрузить статистику");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <div className="admin-dashboard">Загрузка...</div>;
  }

  if (!stats) {
    return <div className="admin-dashboard">Нет данных</div>;
  }

  return (
    <div className="admin-dashboard">
      <h2>Панель администратора</h2>

      <div className="admin-dashboard__grid">
        <div className="admin-stat-card">
          <div className="admin-stat-card__title">Всего пользователей</div>
          <div className="admin-stat-card__value">{stats.total_users}</div>
        </div>

        <div className="admin-stat-card">
          <div className="admin-stat-card__title">Активные сессии</div>
          <div className="admin-stat-card__value">{stats.active_sessions}</div>
        </div>

        <div className="admin-stat-card">
          <div className="admin-stat-card__title">Логи за 24ч</div>
          <div className="admin-stat-card__value">{stats.logs_last_24h}</div>
        </div>

        <div className="admin-stat-card">
          <div className="admin-stat-card__title">Успешных входов (24ч)</div>
          <div className="admin-stat-card__value admin-stat-card__value--success">
            {stats.successful_logins_24h}
          </div>
        </div>

        <div className="admin-stat-card">
          <div className="admin-stat-card__title">Неудачных входов (24ч)</div>
          <div className="admin-stat-card__value admin-stat-card__value--error">
            {stats.failed_logins_24h}
          </div>
        </div>

        <div className="admin-stat-card">
          <div className="admin-stat-card__title">Ошибки за 7д</div>
          <div className="admin-stat-card__value admin-stat-card__value--warning">
            {stats.errors_last_7d}
          </div>
        </div>
      </div>

      {stats.most_active_users.length > 0 && (
        <div className="admin-dashboard__section">
          <h3>Самые активные пользователи (7 дней)</h3>
          <table className="admin-table">
            <thead>
              <tr>
                <th>Пользователь</th>
                <th>Активность</th>
              </tr>
            </thead>
            <tbody>
              {stats.most_active_users.map((user) => (
                <tr key={user.username}>
                  <td>{user.username}</td>
                  <td>{user.activity_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

