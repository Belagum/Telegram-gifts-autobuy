// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { getUserAudit } from "../../entities/admin/api";
import type { AuditLog } from "../../entities/admin/model";
import { Button } from "../../shared/ui/button/Button";
import { showError } from "../../shared/ui/feedback/toast";

export const UserAuditPanel: React.FC = () => {
  const [userId, setUserId] = React.useState("");
  const [logs, setLogs] = React.useState<AuditLog[]>([]);
  const [loading, setLoading] = React.useState(false);

  const handleSearch = async () => {
    const id = parseInt(userId);
    if (isNaN(id)) {
      showError(null, "Введите корректный ID пользователя");
      return;
    }

    try {
      setLoading(true);
      const data = await getUserAudit(id);
      setLogs(data);
    } catch (error) {
      showError(error, "Не удалось загрузить логи пользователя");
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString("ru-RU");
  };

  return (
    <div className="user-audit-panel">
      <h2>Логи пользователя</h2>

      <div className="user-audit-panel__search">
        <input
          type="number"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="Введите ID пользователя"
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
        />
        <Button onClick={handleSearch} disabled={loading}>
          {loading ? "Поиск..." : "Найти"}
        </Button>
      </div>

      {logs.length > 0 && (
        <div className="user-audit-panel__results">
          <h3>Найдено записей: {logs.length}</h3>

          <div className="user-audit-panel__timeline">
            {logs.map((log) => (
              <div key={log.id} className="timeline-item">
                <div className="timeline-item__marker">
                  <span
                    className={log.success ? "status-success" : "status-error"}
                  >
                    {log.success ? "✓" : "✗"}
                  </span>
                </div>
                <div className="timeline-item__content">
                  <div className="timeline-item__header">
                    <strong>{log.action}</strong>
                    <span className="timeline-item__time">
                      {formatDate(log.timestamp)}
                    </span>
                  </div>
                  <div className="timeline-item__details">
                    {log.ip_address && <div>IP: {log.ip_address}</div>}
                    {Object.keys(log.details).length > 0 && (
                      <details>
                        <summary>Подробности</summary>
                        <pre>{JSON.stringify(log.details, null, 2)}</pre>
                      </details>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!loading && logs.length === 0 && userId && (
        <div className="user-audit-panel__empty">
          Логов не найдено для пользователя с ID {userId}
        </div>
      )}
    </div>
  );
};

