// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { Modal } from "./Modal";
import { Button } from "../button/Button";

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  open,
  title,
  message,
  confirmLabel = "Подтвердить",
  cancelLabel = "Отмена",
  onConfirm,
  onCancel,
}) => {
  React.useEffect(() => {
    if (!open) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Enter") {
        event.preventDefault();
        onConfirm();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onConfirm]);

  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      footer={
        <div className="modal-footer-grid">
          <Button variant="ghost" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button variant="danger" onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      }
    >
      <p>{message}</p>
    </Modal>
  );
};
