// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { getSuspiciousActivity } from "../../entities/admin/api";
import type { SuspiciousActivity } from "../../entities/admin/model";
import { showError } from "../../shared/ui/feedback/toast";

export const SuspiciousActivityPanel: React.FC = () => {
  const [activities, setActivities] = React.useState<SuspiciousActivity[]>([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        setLoading(true);
        const data = await getSuspiciousActivity();
        if (!cancelled) {
          setActivities(data);
        }
      } catch (error) {
        if (!cancelled) {
          showError(error, "Не удалось загрузить подозрительную активность");
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

  const getSeverityClass = (severity: string) => {
    switch (severity) {
      case "high":
        return "severity-high";
      case "medium":
        return "severity-medium";
      case "low":
        return "severity-low";
      default:
        return "";
    }
  };

  const getSeverityLabel = (severity: string) => {
    switch (severity) {
      case "high":
        return "Высокая";
      case "medium":
        return "Средняя";
      case "low":
        return "Низкая";
      default:
        return severity;
    }
  };

  if (loading) {
    return <div className="suspicious-activity-panel">Загрузка...</div>;
  }

  return (
    <div className="suspicious-activity-panel">
      <h2>Подозрительная активность</h2>

      {activities.length === 0 ? (
        <div className="suspicious-activity-panel__empty">
          🎉 Подозрительной активности не обнаружено
        </div>
      ) : (
        <div className="suspicious-activity-panel__list">
          {activities.map((activity, index) => (
            <div
              key={index}
              className={`activity-card ${getSeverityClass(activity.severity)}`}
            >
              <div className="activity-card__header">
                <span className="activity-card__severity">
                  {getSeverityLabel(activity.severity)}
                </span>
                <span className="activity-card__type">{activity.activity_type}</span>
              </div>

              <div className="activity-card__description">
                {activity.description}
              </div>

              <div className="activity-card__details">
                <div className="activity-card__detail">
                  <strong>Количество:</strong> {activity.count}
                </div>
                {activity.username && (
                  <div className="activity-card__detail">
                    <strong>Пользователь:</strong> {activity.username} (ID:{" "}
                    {activity.user_id})
                  </div>
                )}
                {activity.ip_address && (
                  <div className="activity-card__detail">
                    <strong>IP:</strong> {activity.ip_address}
                  </div>
                )}
                <div className="activity-card__detail">
                  <strong>Первое событие:</strong> {formatDate(activity.first_seen)}
                </div>
                <div className="activity-card__detail">
                  <strong>Последнее событие:</strong> {formatDate(activity.last_seen)}
                </div>
              </div>

              {Object.keys(activity.details).length > 0 && (
                <details className="activity-card__extra">
                  <summary>Дополнительная информация</summary>
                  <pre>{JSON.stringify(activity.details, null, 2)}</pre>
                </details>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

