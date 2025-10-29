// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { getErrorStats } from "../../entities/admin/api";
import type { ErrorStats } from "../../entities/admin/model";
import { showError } from "../../shared/ui/feedback/toast";

export const ErrorStatsPanel: React.FC = () => {
  const [stats, setStats] = React.useState<ErrorStats[]>([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        setLoading(true);
        const data = await getErrorStats();
        if (!cancelled) {
          setStats(data);
        }
      } catch (error) {
        if (!cancelled) {
          showError(error, "Не удалось загрузить статистику ошибок");
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

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString("ru-RU");
  };

  if (loading) {
    return <div className="error-stats-panel">Загрузка...</div>;
  }

  return (
    <div className="error-stats-panel">
      <h2>Статистика ошибок по IP</h2>

      {stats.length === 0 ? (
        <div className="error-stats-panel__empty">
          Ошибок за последние 24 часа не обнаружено
        </div>
      ) : (
        <div className="error-stats-panel__table-container">
          <table className="admin-table">
            <thead>
              <tr>
                <th>IP адрес</th>
                <th>Всего ошибок</th>
                <th>Уникальных действий</th>
                <th>Первая ошибка</th>
                <th>Последняя ошибка</th>
                <th>Примеры ошибок</th>
              </tr>
            </thead>
            <tbody>
              {stats.map((stat, index) => (
                <tr key={index}>
                  <td>{stat.ip_address || "Неизвестно"}</td>
                  <td>
                    <strong className="error-count">{stat.error_count}</strong>
                  </td>
                  <td>{stat.unique_actions}</td>
                  <td>{formatDate(stat.first_error)}</td>
                  <td>{formatDate(stat.last_error)}</td>
                  <td>
                    <details>
                      <summary>Показать ({stat.sample_errors.length})</summary>
                      <ul className="error-list">
                        {stat.sample_errors.map((error, i) => (
                          <li key={i}>{error}</li>
                        ))}
                      </ul>
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

