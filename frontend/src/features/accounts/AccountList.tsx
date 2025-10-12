// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { Button } from "../../shared/ui/button/Button";
import { Skeleton } from "../../shared/ui/skeleton/Skeleton";
import { Account } from "../../entities/accounts/model";
import { refreshAccountStream } from "../../entities/accounts/api";
import { upsertLoadingToast, completeToast, failToast } from "../../shared/ui/feedback/toast";
import "./account-list.css";

export interface AccountListProps {
  accounts: Account[];
  onReload: () => void;
  isLoading?: boolean;
}

export const AccountList: React.FC<AccountListProps> = ({ accounts, onReload, isLoading = false }) => {
  const [items, setItems] = React.useState<Account[]>(accounts);
  const [loadingId, setLoadingId] = React.useState<number | null>(null);
  const [isBoot, setBoot] = React.useState(!accounts.length);

  React.useEffect(() => {
    setItems(accounts);
    setBoot(false);
  }, [accounts]);

  const handleRefresh = async (id: number) => {
    if (loadingId === id) return;
    setLoadingId(id);
    
    const toastId = `acc-refresh-${id}`;
    upsertLoadingToast(toastId, "Обновление аккаунта...");

    const refreshPromise = new Promise<void>((resolve, reject) => {
      refreshAccountStream(id, (event) => {
        if (event.message || event.stage) {
          const msg = event.message || `Этап: ${event.stage}`;
          upsertLoadingToast(toastId, msg);
        }
        if (event.error) {
          reject(new Error(event.detail || event.error || "Ошибка при обновлении аккаунта."));
        }
        if (event.done && event.account) {
          setItems((prev) => prev.map((item) => (item.id === id ? event.account! : item)));
          resolve();
        }
      });
    });

    refreshPromise
      .then(() => completeToast(toastId, "Аккаунт успешно обновлён"))
      .catch((err) => failToast(toastId, err?.message || "Не удалось обновить аккаунт"))
      .finally(() => {
        setLoadingId(null);
        onReload();
      });
  };

  if (isBoot) {
    return (
      <div className="account-grid">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="account-card">
            <Skeleton height={22} width="60%" />
            <Skeleton height={16} width="40%" />
            <Skeleton height={16} width="50%" />
            <Skeleton height={16} width="80%" />
            <Skeleton height={40} width="100%" />
          </div>
        ))}
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="account-empty">
        {isLoading ? "Обновление..." : "Нет аккаунтов"}
      </div>
    );
  }

  return (
    <div className="account-grid">
      {items.map((account) => (
        <div key={account.id} className="account-card">
          <div className="account-card__header">
            <h3>{account.displayName}</h3>
            <span className="account-card__username">@{account.username ?? "нет имени"}</span>
          </div>
          <div className="account-card__row">
            <span>Звёзды:</span>
            <span>{account.stars}</span>
          </div>
          <div className="account-card__row">
            <span>Премиум:</span>
            <span>
              {account.isPremium
                ? `до ${account.premiumUntil ?? "?"}`
                : "Нет"}
            </span>
          </div>
          <div className="account-card__updated">
            Последнее обновление: {account.lastCheckedAt ? new Date(account.lastCheckedAt).toLocaleString() : "нет данных"}
          </div>
          <Button
            variant="secondary"
            onClick={() => handleRefresh(account.id)}
            loading={loadingId === account.id}
            disabled={loadingId === account.id}
          >
            {loadingId === account.id ? "Обновление..." : "Обновить"}
          </Button>
        </div>
      ))}
    </div>
  );
};
