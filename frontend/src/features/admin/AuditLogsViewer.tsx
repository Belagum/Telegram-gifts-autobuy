// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { getActionCategories, getAuditLogs } from "../../entities/admin/api";
import type { AuditLog, AuditLogsFilter } from "../../entities/admin/model";
import { Button } from "../../shared/ui/button/Button";
import { showError } from "../../shared/ui/feedback/toast";

export const AuditLogsViewer: React.FC = () => {
  const [logs, setLogs] = React.useState<AuditLog[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(false);
  const [actions, setActions] = React.useState<string[]>([]);

  const [filter, setFilter] = React.useState<AuditLogsFilter>({
    limit: 50,
    offset: 0,
  });

  const loadLogs = React.useCallback(async (currentFilter: AuditLogsFilter) => {
    try {
      setLoading(true);
      const data = await getAuditLogs(currentFilter);
      setLogs(data.logs);
      setTotal(data.total);
    } catch (error) {
      showError(error, "Не удалось загрузить логи");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const categories = await getActionCategories();
        if (!cancelled) {
          setActions(categories);
        }
      } catch (error) {
        if (!cancelled) {
          showError(error, "Не удалось загрузить категории");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    void loadLogs(filter);
  }, [filter, loadLogs]);

  const handleFilterChange = (key: keyof AuditLogsFilter, value: any) => {
    setFilter((prev) => ({ ...prev, [key]: value, offset: 0 }));
  };

  const handleNextPage = () => {
    setFilter((prev) => ({
      ...prev,
      offset: (prev.offset || 0) + (prev.limit || 50),
    }));
  };

  const handlePrevPage = () => {
    setFilter((prev) => ({
      ...prev,
      offset: Math.max(0, (prev.offset || 0) - (prev.limit || 50)),
    }));
  };

  const handleClearFilters = () => {
    setFilter({ limit: 50, offset: 0 });
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString("ru-RU");
  };

  const currentPage = Math.floor((filter.offset || 0) / (filter.limit || 50)) + 1;
  const totalPages = Math.ceil(total / (filter.limit || 50));

  return (
    <div className="audit-logs-viewer">
      <h2>Журнал аудита</h2>

      <div className="audit-logs-viewer__filters">
        <div className="filter-group">
          <label>Действие:</label>
          <select
            value={filter.action || ""}
            onChange={(e) =>
              handleFilterChange("action", e.target.value || undefined)
            }
          >
            <option value="">Все</option>
            {actions.map((action) => (
              <option key={action} value={action}>
                {action}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label>User ID:</label>
          <input
            type="number"
            value={filter.user_id || ""}
            onChange={(e) =>
              handleFilterChange(
                "user_id",
                e.target.value ? parseInt(e.target.value) : undefined
              )
            }
            placeholder="ID пользователя"
          />
        </div>

        <div className="filter-group">
          <label>IP адрес:</label>
          <input
            type="text"
            value={filter.ip_address || ""}
            onChange={(e) =>
              handleFilterChange("ip_address", e.target.value || undefined)
            }
            placeholder="IP адрес"
          />
        </div>

        <div className="filter-group">
          <label>Статус:</label>
          <select
            value={
              filter.success === undefined
                ? ""
                : filter.success
                  ? "true"
                  : "false"
            }
            onChange={(e) =>
              handleFilterChange(
                "success",
                e.target.value === ""
                  ? undefined
                  : e.target.value === "true"
              )
            }
          >
            <option value="">Все</option>
            <option value="true">Успех</option>
            <option value="false">Ошибка</option>
          </select>
        </div>

        <Button variant="secondary" onClick={handleClearFilters}>
          Сбросить
        </Button>
      </div>

      {loading && <div className="audit-logs-viewer__loading">Загрузка...</div>}

      {!loading && (
        <>
          <div className="audit-logs-viewer__info">
            Всего записей: {total} | Показано: {logs.length} | Страница{" "}
            {currentPage} из {totalPages}
          </div>

          <div className="audit-logs-viewer__table-container">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Время</th>
                  <th>Действие</th>
                  <th>User ID</th>
                  <th>IP адрес</th>
                  <th>Статус</th>
                  <th>Детали</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td>{log.id}</td>
                    <td>{formatDate(log.timestamp)}</td>
                    <td>{log.action}</td>
                    <td>{log.user_id || "-"}</td>
                    <td>{log.ip_address || "-"}</td>
                    <td>
                      <span
                        className={
                          log.success ? "status-success" : "status-error"
                        }
                      >
                        {log.success ? "✓" : "✗"}
                      </span>
                    </td>
                    <td>
                      <details>
                        <summary>Подробнее</summary>
                        <pre>{JSON.stringify(log.details, null, 2)}</pre>
                      </details>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="audit-logs-viewer__pagination">
            <Button
              variant="secondary"
              onClick={handlePrevPage}
              disabled={(filter.offset || 0) === 0}
            >
              ← Назад
            </Button>
            <span>
              Страница {currentPage} из {totalPages}
            </span>
            <Button
              variant="secondary"
              onClick={handleNextPage}
              disabled={(filter.offset || 0) + (filter.limit || 50) >= total}
            >
              Вперед →
            </Button>
          </div>
        </>
      )}
    </div>
  );
};

