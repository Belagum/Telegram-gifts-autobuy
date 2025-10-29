// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { Button } from "../../shared/ui/button/Button";
import { AccountList } from "../../features/accounts/AccountList";
import { listAccounts } from "../../entities/accounts/api";
import type { Account } from "../../entities/accounts/model";
import { listApiProfiles } from "../../entities/accounts/apiProfiles";
import type { ApiProfile } from "../../entities/accounts/apiProfile";
import { AddApiProfileModal } from "../../features/accounts/AddApiProfileModal";
import { AddAccountModal } from "../../features/accounts/AddAccountModal";
import { SelectApiProfileModal } from "../../features/accounts/SelectApiProfileModal";
import { ChannelsModal } from "../../features/settings/ChannelsModal";
import { showError } from "../../shared/ui/feedback/toast";
import { openCentered } from "../../shared/lib/utils/openCentered";
import { useIsAdmin } from "../../features/auth/hooks/useIsAdmin";
import "./dashboard.css";

export const DashboardPage: React.FC = () => {
  const [accounts, setAccounts] = React.useState<Account[]>([]);
  const [apiProfiles, setApiProfiles] = React.useState<ApiProfile[]>([]);
  const [apiModalOpen, setApiModalOpen] = React.useState(false);
  const [selectModalOpen, setSelectModalOpen] = React.useState(false);
  const [accountModalOpen, setAccountModalOpen] = React.useState(false);
  const [channelsOpen, setChannelsOpen] = React.useState(false);
  const [selectedApiProfile, setSelectedApiProfile] = React.useState<number | null>(null);
  const [pendingAccountModal, setPendingAccountModal] = React.useState(false);
  const [isLoadingAccounts, setIsLoadingAccounts] = React.useState(false);
  const { isAdmin } = useIsAdmin();

  const loadAccounts = React.useCallback(async () => {
    try {
      setIsLoadingAccounts(true);
      const items = await listAccounts();
      setAccounts(items);
    } catch (error) {
      showError(error, "Не удалось загрузить аккаунты");
    } finally {
      setIsLoadingAccounts(false);
    }
  }, []);

  const refreshApiProfiles = React.useCallback(async () => {
    try {
      const items = await listApiProfiles();
      setApiProfiles(items);
    } catch (error) {
      showError(error, "Не удалось загрузить профили");
    }
  }, []);

  const loadedRef = React.useRef(false);
  React.useEffect(() => {
    if (loadedRef.current) return;
    loadedRef.current = true;
    void loadAccounts();
    return () => {
      loadedRef.current = false;
    };
  }, [loadAccounts]);

  React.useEffect(() => {
    if (pendingAccountModal && selectedApiProfile !== null) {
      setAccountModalOpen(true);
      setPendingAccountModal(false);
    }
  }, [selectedApiProfile, pendingAccountModal]);

  const handleAddAccount = async () => {
    await refreshApiProfiles();
    setSelectModalOpen(true);
  };

  const handleChooseApiProfile = (id: number) => {
    setSelectedApiProfile(id);
    setSelectModalOpen(false);
    setPendingAccountModal(true);
  };

  const handleApiSaved = (id: number) => {
    void refreshApiProfiles();
    handleChooseApiProfile(id);
  };

  const handleAccountAdded = () => {
    setAccountModalOpen(false);
    setSelectedApiProfile(null);
    void loadAccounts();
  };

  const openGifts = () => openCentered("/gifts?popup=1", "gifts", 520, 700);
  const openSettings = () => openCentered("/settings?popup=1", "settings", 520, 600);
  const openAdmin = () => openCentered("/admin?popup=1", "admin", 1200, 800);

  return (
    <div className="dashboard">
      <header className="dashboard__header">
        <h1>TG Gifts</h1>
        <div className="dashboard__actions">
          {isAdmin && (
            <Button variant="secondary" onClick={openAdmin}>
              Админ-панель
            </Button>
          )}
          <Button variant="secondary" onClick={() => setChannelsOpen(true)}>
            Каналы
          </Button>
          <Button variant="secondary" onClick={openSettings}>
            Настройки
          </Button>
          {accounts.length > 0 && (
            <Button variant="secondary" onClick={openGifts}>
              Подарки
            </Button>
          )}
          <Button onClick={handleAddAccount}>Добавить аккаунт</Button>
        </div>
      </header>
      <AccountList accounts={accounts} onReload={loadAccounts} isLoading={isLoadingAccounts} />

      <SelectApiProfileModal
        open={selectModalOpen}
        items={apiProfiles}
        onChoose={handleChooseApiProfile}
        onAddNew={() => {
          setSelectModalOpen(false);
          setApiModalOpen(true);
        }}
        onClose={() => setSelectModalOpen(false)}
      />
      <AddApiProfileModal
        open={apiModalOpen}
        onClose={() => setApiModalOpen(false)}
        onSaved={handleApiSaved}
      />
      <AddAccountModal
        open={accountModalOpen}
        apiProfileId={selectedApiProfile}
        onClose={() => {
          setAccountModalOpen(false);
          setSelectedApiProfile(null);
        }}
        onSuccess={handleAccountAdded}
      />
      <ChannelsModal open={channelsOpen} onClose={() => setChannelsOpen(false)} />
    </div>
  );
};
