// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova orig

import { toast } from "react-toastify";

const TOAST_MIN_INTERVAL_MS = 1000;

let _activeId = null;
let _lastShownAt = 0;
let _timer = null;

function _errorText(e, fallback = "Ошибка") {
  if (!e) return fallback;
  if (typeof e === "string") return e;
  if (e.error_code && e.detail) return `${e.error_code}: ${e.detail}`;
  if (e.error_code) return String(e.error_code);
  return e.detail || e.error || e.message || fallback;
}

function _ensureActiveId() {
  if (_activeId && !toast.isActive(_activeId)) {
    _activeId = null;
  }
}

function _scheduleShow(updater) {
  const now = Date.now();
  const wait = Math.max(0, TOAST_MIN_INTERVAL_MS - (now - _lastShownAt));
  if (_timer) clearTimeout(_timer);
  _timer = setTimeout(() => {
    _timer = null;
    // важная проверка: могли успеть закрыть
    _ensureActiveId();
    updater();
    _lastShownAt = Date.now();
  }, wait);
}

function _createToast({ render, type, isLoading, autoClose }) {
  const common = {
    autoClose,
    closeOnClick: !isLoading,
    onClose: () => {
      // если закрыли активный — забываем id
      if (_activeId && !toast.isActive(_activeId)) {
        _activeId = null;
      }
    }
  };
  const id = isLoading
    ? toast.loading(render, common)
    : toast(render, { type, ...common });
  _activeId = id;
}

function _ensureOneToast({
  render,
  type = "default",
  isLoading = false,
  autoClose = 2000,
  updateOnly = false
} = {}) {
  _scheduleShow(() => {
    // перед работой проверим актуальность id
    _ensureActiveId();

    if (_activeId && updateOnly) {
      toast.update(_activeId, {
        render,
        type,
        isLoading,
        autoClose,
        closeOnClick: !isLoading
      });
      return;
    }

    if (_activeId) {
      // обновляем существующий
      toast.update(_activeId, {
        render,
        type,
        isLoading,
        autoClose,
        closeOnClick: !isLoading
      });
    } else {
      // создаём новый
      _createToast({ render, type, isLoading, autoClose });
    }
  });
}

/**
 * Единственный тост на весь поток:
 * - pendingMessage: строка или null/"" чтобы НЕ показывать pending.
 * - successMessage: строка или (res)=>строка
 * - errorMessage:   строка или (err)=>строка
 */
export function showPromise(
  promise,
  pendingMessage = "",
  successMessage = "Готово",
  errorMessage = "Ошибка"
) {
  // pending по умолчанию скрыт — создаём лоадер, только если нет активного
  if (pendingMessage) {
    _ensureOneToast({
      render: pendingMessage,
      type: "info",
      isLoading: true,
      autoClose: false
    });
  } else {
    _ensureActiveId();
    if (!_activeId) {
      _ensureOneToast({
        render: "…",
        type: "info",
        isLoading: true,
        autoClose: false
      });
    }
  }

  return promise
    .then((res) => {
      const msg =
        typeof successMessage === "function" ? successMessage(res) : successMessage;
      // если активного уже нет (закрылся) — покажем новый «успех»
      _ensureActiveId();
      _ensureOneToast({
        render: msg,
        type: "success",
        isLoading: false,
        autoClose: 1500,
        updateOnly: !!_activeId
      });
      return res;
    })
    .catch((err) => {
      const base = typeof errorMessage === "function" ? errorMessage(err) : errorMessage;
      const msg = _errorText(err, base);
      _ensureActiveId();
      _ensureOneToast({
        render: msg,
        type: "error",
        isLoading: false,
        autoClose: 2500,
        updateOnly: !!_activeId
      });
      throw err;
    });
}

// Шорткаты — тоже один тост с троттлингом/заменой
export function showInfo(message) {
  _ensureActiveId();
  _ensureOneToast({ render: message, type: "info", isLoading: false, autoClose: 2000 });
}
export function showSuccess(message) {
  _ensureActiveId();
  _ensureOneToast({ render: message, type: "success", isLoading: false, autoClose: 1500 });
}
export function showError(err, fallback = "Ошибка") {
  _ensureActiveId();
  _ensureOneToast({ render: _errorText(err, fallback), type: "error", isLoading: false, autoClose: 2500 });
}

// Ручная очистка
export function dismissAll() {
  if (_timer) { clearTimeout(_timer); _timer = null; }
  if (_activeId) { toast.dismiss(_activeId); _activeId = null; }
}
