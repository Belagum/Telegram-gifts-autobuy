// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { Modal } from "../../shared/ui/modal/Modal";
import { FormField } from "../../shared/ui/form-field/FormField";
import { Input } from "../../shared/ui/input/Input";
import { Button } from "../../shared/ui/button/Button";
import {
  cancelLogin,
  confirmCode,
  confirmPassword,
  sendCode,
  type ConfirmCodeResponse,
  type ConfirmPasswordResponse,
  type SendCodeResponse,
} from "../auth/telegramLoginApi";
import { showError, showInfo, showPromise } from "../../shared/ui/feedback/toast";
import { extractApiErrorMessage } from "../../shared/api/errorMessages";

export interface AddAccountModalProps {
  apiProfileId: number | null;
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

type Step = "phone" | "code" | "password";

export const AddAccountModal: React.FC<AddAccountModalProps> = ({ apiProfileId, open, onClose, onSuccess }) => {
  const [step, setStep] = React.useState<Step>("phone");
  const [loginId, setLoginId] = React.useState<string>("");
  const [phone, setPhone] = React.useState<string>("");
  const [code, setCode] = React.useState<string>("");
  const [password, setPassword] = React.useState<string>("");
  const [busy, setBusy] = React.useState<Step | "cancel" | null>(null);

  React.useEffect(() => {
    if (!open) {
      setStep("phone");
      setPhone("");
      setCode("");
      setPassword("");
      setLoginId("");
    }
  }, [open]);

  const handleSendCode = async () => {
    if (!apiProfileId) {
      showError({ error: "Сначала выберите API профиль" });
      return;
    }
    if (!phone.trim()) {
      showError({ error: "Введите номер телефона" });
      return;
    }
    setBusy("phone");
    try {
      const promise = sendCode({ api_profile_id: apiProfileId, phone });
      showPromise(
        promise, 
        "Отправляю код…", 
        "Код отправлен", 
        (err) => extractApiErrorMessage(err, "Ошибка отправки кода")
      );
      const result: SendCodeResponse = await promise;
      setLoginId(result.login_id);
      setStep("code");
    } finally {
      setBusy(null);
    }
  };

  const handleConfirmCode = async () => {
    if (!code.trim()) {
      showError({ error: "Введите код" });
      return;
    }
    setBusy("code");
    try {
      const promise = confirmCode({ login_id: loginId, code });
      showPromise(
        promise, 
        "Проверяю код…", 
        "Код подтверждён", 
        (err) => extractApiErrorMessage(err, "Ошибка подтверждения")
      );
      const result: ConfirmCodeResponse = await promise;
      if (result?.need_2fa) {
        setStep("password");
        showInfo("Требуется пароль 2FA");
      } else if (result?.ok) {
        onSuccess();
        onClose();
      } else {
        showError(result, "Ошибка подтверждения");
        if (result?.should_close_modal) {
          onClose();
        }
      }
    } catch (error) {
      const httpError = error as { payload?: ConfirmCodeResponse };
      if (httpError?.payload?.should_close_modal) {
        onClose();
      }
    } finally {
      setBusy(null);
    }
  };

  const handleConfirmPassword = async () => {
    if (!password) {
      showError({ error: "Введите пароль" });
      return;
    }
    setBusy("password");
    try {
      const promise = confirmPassword({ login_id: loginId, password });
      showPromise(
        promise, 
        "Входим…", 
        "Аккаунт добавлен", 
        (err) => extractApiErrorMessage(err, "Ошибка пароля")
      );
      const result: ConfirmPasswordResponse = await promise;
      if (result?.ok) {
        onSuccess();
        onClose();
      } else {
        showError(result, "Ошибка пароля");
        if (result?.should_close_modal) {
          onClose();
        }
      }
    } catch (error) {
      const httpError = error as { payload?: ConfirmPasswordResponse };
      if (httpError?.payload?.should_close_modal) {
        onClose();
      }
    } finally {
      setBusy(null);
    }
  };

  const handleCancel = async () => {
    setBusy("cancel");
    try {
      if (loginId) {
        const promise = cancelLogin({ login_id: loginId });
        showPromise(
          promise, 
          "Отменяю…", 
          "Вход отменён", 
          (err) => extractApiErrorMessage(err, "Не удалось отменить")
        );
        await promise;
      }
    } finally {
      setBusy(null);
      onClose();
    }
  };

  const footer = (
    <div className="modal-footer-grid">
      <Button variant="ghost" onClick={handleCancel} disabled={busy !== null}>
        Отмена
      </Button>
      {step === "phone" && (
        <Button onClick={handleSendCode} loading={busy === "phone"} disabled={busy !== null}>
          Отправить код
        </Button>
      )}
      {step === "code" && (
        <Button onClick={handleConfirmCode} loading={busy === "code"} disabled={busy !== null}>
          Подтвердить код
        </Button>
      )}
      {step === "password" && (
        <Button onClick={handleConfirmPassword} loading={busy === "password"} disabled={busy !== null}>
          Войти
        </Button>
      )}
    </div>
  );

  return (
    <Modal open={open} onClose={handleCancel} title="Добавить аккаунт" footer={footer}>
      {step === "phone" && (
        <FormField label="Телефон" description="Формат +79998887766" required>
          <Input 
            value={phone} 
            onChange={(event) => setPhone(event.target.value)} 
            onKeyDown={(event) => {
              if (event.key === "Enter" && busy === null) {
                event.preventDefault();
                handleSendCode();
              }
            }}
            disabled={busy !== null} 
          />
        </FormField>
      )}
      {step === "code" && (
        <FormField label="Код из Telegram" required>
          <Input 
            value={code} 
            onChange={(event) => setCode(event.target.value)} 
            onKeyDown={(event) => {
              if (event.key === "Enter" && busy === null) {
                event.preventDefault();
                handleConfirmCode();
              }
            }}
            disabled={busy !== null} 
          />
        </FormField>
      )}
      {step === "password" && (
        <FormField label="Пароль 2FA" required>
          <Input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && busy === null) {
                event.preventDefault();
                handleConfirmPassword();
              }
            }}
            disabled={busy !== null}
          />
        </FormField>
      )}
    </Modal>
  );
};
