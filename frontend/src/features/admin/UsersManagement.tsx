// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { listUsers, unlockUser } from "../../entities/admin/api";
import type { UserInfo } from "../../entities/admin/model";
import { Button } from "../../shared/ui/button/Button";
import { showError, showSuccess } from "../../shared/ui/feedback/toast";

export const UsersManagement: React.FC = () => {
  const [users, setUsers] = React.useState<UserInfo[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [unlocking, setUnlocking] = React.useState<number | null>(null);

  const loadUsers = React.useCallback(async () => {
    try {
      setLoading(true);
      const data = await listUsers();
      setUsers(data);
    } catch (error) {
      showError(error, "Не удалось загрузить список пользователей");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  const handleUnlock = async (userId: number, username: string) => {
    try {
      setUnlocking(userId);
      await unlockUser(userId);
      showSuccess(`Пользователь ${username} разблокирован`);
      await loadUsers();
    } catch (error) {
      showError(error, "Не удалось разблокировать пользователя");
    } finally {
      setUnlocking(null);
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "-";
    const date = new Date(dateStr);
    return date.toLocaleString("ru-RU");
  };

  if (loading) {
    return <div className="users-management">Загрузка...</div>;
  }

  return (
    <div className="users-management">
      <h2>Управление пользователями</h2>

      <div className="users-management__info">Всего пользователей: {users.length}</div>

      <div className="users-management__table-container">
        <table className="admin-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Имя пользователя</th>
              <th>Админ</th>
              <th>Создан</th>
              <th>Последний вход</th>
              <th>Статус</th>
              <th>Неудачных попыток</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>{user.id}</td>
                <td>
                  <strong>{user.username}</strong>
                </td>
                <td>{user.is_admin ? "✓" : "-"}</td>
                <td>{formatDate(user.created_at)}</td>
                <td>{formatDate(user.last_login)}</td>
                <td>
                  {user.is_locked ? (
                    <span className="user-status user-status--locked">
                      Заблокирован
                    </span>
                  ) : (
                    <span className="user-status user-status--active">Активен</span>
                  )}
                </td>
                <td>
                  {user.failed_attempts > 0 ? (
                    <span className="failed-attempts">{user.failed_attempts}</span>
                  ) : (
                    "-"
                  )}
                </td>
                <td>
                  {user.is_locked && (
                    <Button
                      variant="secondary"
                      onClick={() => handleUnlock(user.id, user.username)}
                      disabled={unlocking === user.id}
                    >
                      {unlocking === user.id ? "..." : "Разблокировать"}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

