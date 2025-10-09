// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import { toast } from "react-toastify";
import type { ApiErrorDto } from "../../api/dto";

export const showSuccess = (message: string) => toast.success(message);

export const showInfo = (message: string) => toast.info(message);

const activeToastIds = new Set<string>();

export const showError = (error: unknown, fallback = "Что-то пошло не так, попробуйте ещё раз") => {
  const payload = error as ApiErrorDto & { detail?: string };
  const message = payload?.detail || payload?.error || fallback;
  const id = `err-${message}`;
  if (activeToastIds.has(id)) return;
  activeToastIds.add(id);
  toast.error(message, {
    toastId: id,
    onClose: () => activeToastIds.delete(id),
  });
};

export const showPromise = <T,>(promise: Promise<T>, pending: string, success: string, error: string) =>
  toast.promise(promise, {
    pending,
    success,
    error,
  });

export const upsertLoadingToast = (id: string, message: string) => {
  if (toast.isActive(id)) {
    toast.update(id, { render: message, isLoading: true });
  } else {
    toast.loading(message, { toastId: id });
  }
};

export const completeToast = (id: string, message: string) => {
  toast.update(id, { render: message, type: "success", isLoading: false, autoClose: 2000 });
};

export const failToast = (id: string, message: string) => {
  toast.update(id, { render: message, type: "error", isLoading: false, autoClose: 4000 });
};
