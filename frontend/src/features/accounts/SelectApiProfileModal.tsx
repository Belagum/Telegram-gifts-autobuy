// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { Modal } from "../../shared/ui/modal/Modal";
import { Button } from "../../shared/ui/button/Button";
import { ConfirmDialog } from "../../shared/ui/modal/ConfirmDialog";
import type { ApiProfile } from "../../entities/accounts/apiProfile";
import { deleteApiProfile, renameApiProfile } from "../../entities/accounts/apiProfiles";
import type { HttpError } from "../../shared/api/httpClient";
import { showError, showSuccess } from "../../shared/ui/feedback/toast";
import "./select-api-modal.css";

export interface SelectApiProfileModalProps {
  open: boolean;
  items: ApiProfile[];
  onChoose: (id: number) => void;
  onAddNew: () => void;
  onClose: () => void;
}

export const SelectApiProfileModal: React.FC<SelectApiProfileModalProps> = ({
  open,
  items,
  onChoose,
  onAddNew,
  onClose,
}) => {
  const [list, setList] = React.useState<ApiProfile[]>(items);
  const [editingId, setEditingId] = React.useState<number | null>(null);
  const [editValue, setEditValue] = React.useState<string>("");
  const [confirm, setConfirm] = React.useState<ApiProfile | null>(null);
  const editInputRef = React.useRef<HTMLInputElement | null>(null);

  React.useEffect(() => {
    setList(items);
  }, [items]);

  const startEdit = (profile: ApiProfile) => {
    setEditingId(profile.id);
    setEditValue(profile.name || `API ${profile.apiId}`);
  };

  const submitEdit = async () => {
    if (!editingId) return;
    const target = list.find((item) => item.id === editingId);
    if (!target) {
      setEditingId(null);
      return;
    }
    const next = editValue.trim();
    const prev = (target.name || `API ${target.apiId}`).trim();
    if (!next || next === prev) {
      setEditingId(null);
      return;
    }
    try {
      const updated = await renameApiProfile(editingId, next);
      setList((current) =>
        current.map((item) => {
          if (item.id !== editingId) return item;
          const merged = { ...item, ...updated };
          merged.name = (updated as typeof item).name ?? next;
          return merged;
        }),
      );
      showSuccess("Название обновлено");
    } catch (error) {
      showError(error, "Не удалось обновить");
    } finally {
      setEditingId(null);
    }
  };

  const extractErrorCode = (error: unknown): string | undefined => {
    if (typeof error !== "object" || error === null) {
      return undefined;
    }
    const httpError = error as Partial<HttpError>;
    const payload = httpError.payload;
    if (typeof payload !== "object" || payload === null) {
      return undefined;
    }
    const maybePayload = payload as { error?: unknown };
    return typeof maybePayload.error === "string" ? maybePayload.error : undefined;
  };

  const handleDelete = async () => {
    if (!confirm) return;
    try {
      await deleteApiProfile(confirm.id);
      setList((current) => current.filter((item) => item.id !== confirm.id));
      showSuccess("API удалён");
    } catch (error: unknown) {
      const code = extractErrorCode(error);
      const fallback = code === "api_profile_in_use" ? "API используется аккаунтами" : "Не удалось удалить";
      showError(error, fallback);
    } finally {
      setConfirm(null);
    }
  };

  React.useEffect(() => {
    if (editingId) {
      editInputRef.current?.focus();
      editInputRef.current?.select();
    }
  }, [editingId]);

  const renderItem = (item: ApiProfile) => {
    const isEditing = editingId === item.id;
    const name = item.name || `API ${item.apiId}`;
    return (
      <div key={item.id} className="api-item">
        {isEditing ? (
          <div className="api-item__content">
            <input
              ref={editInputRef}
              className="api-item__input"
              value={editValue}
              onChange={(event) => setEditValue(event.target.value)}
              onBlur={submitEdit}
              onKeyDown={(event) => {
                if (event.key === "Enter") submitEdit();
                if (event.key === "Escape") setEditingId(null);
              }}
            />
          </div>
        ) : (
          <button
            type="button"
            className="api-item__content"
            onClick={() => onChoose(item.id)}
          >
            <span>{name}</span>
          </button>
        )}
        <div className="api-item__actions">
          <Button size="sm" variant="ghost" onClick={() => startEdit(item)}>
            Переименовать
          </Button>
          <Button size="sm" variant="danger" onClick={() => setConfirm(item)}>
            Удалить
          </Button>
        </div>
      </div>
    );
  };

  return (
    <>
      <Modal
        open={open}
        onClose={onClose}
        title="Выберите API профиль"
        footer={
          <Button variant="secondary" onClick={onAddNew}>
            Добавить новый API
          </Button>
        }
      >
        <div className="api-list">
          {list.length === 0 && <div className="api-list__empty">Профилей нет</div>}
          {list.map(renderItem)}
        </div>
      </Modal>
      <ConfirmDialog
        open={Boolean(confirm)}
        title="Удалить API профиль?"
        message={`«${confirm?.name || `API ${confirm?.apiId}`}» будет удалён. Если он используется аккаунтами — удаление запрещено.`}
        onCancel={() => setConfirm(null)}
        onConfirm={handleDelete}
        confirmLabel="Удалить"
      />
    </>
  );
};
