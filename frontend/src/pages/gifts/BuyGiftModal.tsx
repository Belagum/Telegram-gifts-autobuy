// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { Modal } from "../../shared/ui/modal/Modal";
import { Button } from "../../shared/ui/button/Button";
import { Input } from "../../shared/ui/input/Input";
import type { Gift } from "../../entities/gifts/model";
import type { Account } from "../../entities/accounts/model";
import { buyGift } from "../../entities/gifts/api";
import type { HttpError } from "../../shared/api/httpClient";

export interface BuyGiftModalProps {
  open: boolean;
  gift: Gift | null;
  accounts: Account[];
  onClose: () => void;
  onPurchased?: () => Promise<void> | void;
}

type Step = "accounts" | "target" | "loading" | "result";

const dateFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const resolveAccountLabel = (account: Account) => {
  if (account.username) {
    const nick = account.username.startsWith("@") ? account.username : `@${account.username}`;
    return `${nick} (${account.id})`;
  }
  return `${account.id}`;
};

const extractErrorMessage = (error: unknown) => {
  if (!error) {
    return "Не удалось купить подарок";
  }
  const http = error as HttpError;
  const payload = (http && typeof http === "object" ? http.payload : null) as
    | { detail?: string; error?: string; message?: string }
    | undefined;
  if (payload) {
    return payload.detail || payload.message || payload.error || "Не удалось купить подарок";
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Не удалось купить подарок";
};

export const BuyGiftModal: React.FC<BuyGiftModalProps> = ({
  open,
  gift,
  accounts,
  onClose,
  onPurchased,
}) => {
  const [step, setStep] = React.useState<Step>("accounts");
  const [selectedAccount, setSelectedAccount] = React.useState<Account | null>(null);
  const [targetId, setTargetId] = React.useState("");
  const [inputError, setInputError] = React.useState<string | null>(null);
  const [resultMessage, setResultMessage] = React.useState<string>("");
  const [resultOk, setResultOk] = React.useState<boolean>(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (!open) {
      setStep("accounts");
      setSelectedAccount(null);
      setTargetId("");
      setInputError(null);
      setResultMessage("");
      setResultOk(false);
      return;
    }
    setStep("accounts");
    setSelectedAccount(null);
    setTargetId("");
    setInputError(null);
    setResultMessage("");
    setResultOk(false);
  }, [open, gift?.id]);

  const handleSelectAccount = (account: Account) => {
    setSelectedAccount(account);
    setStep("target");
  };

  React.useEffect(() => {
    if (open && step === "target") {
      inputRef.current?.focus({ preventScroll: true });
    }
  }, [open, step]);

  const handleSubmit = async () => {
    const normalized = targetId.trim();
    if (!normalized) {
      setInputError("Введите ID получателя");
      return;
    }
    if (!selectedAccount || !gift) {
      setInputError("Выберите аккаунт");
      return;
    }
    setInputError(null);
    setStep("loading");
    try {
      const response = await buyGift({
        giftId: gift.id,
        accountId: selectedAccount.id,
        targetId: normalized,
      });
      if (!response.ok) {
        throw new Error(response.detail || response.message || response.error || "Ошибка покупки");
      }
      setResultOk(true);
      setResultMessage(response.message || "Подарок успешно куплен");
      setStep("result");
      await onPurchased?.();
    } catch (error) {
      setResultOk(false);
      setResultMessage(extractErrorMessage(error));
      setStep("result");
    }
  };

  const renderAccounts = () => (
    <div className="buy-modal__section">
      <p className="buy-modal__hint">Выберите аккаунт, с которого отправить подарок:</p>
      <div className="buy-modal__accounts">
        {accounts.map((account) => (
          <Button
            key={account.id}
            variant="secondary"
            className="buy-modal__account"
            onClick={() => handleSelectAccount(account)}
          >
            {resolveAccountLabel(account)}
          </Button>
        ))}
        {accounts.length === 0 && (
          <div className="buy-modal__empty">Нет доступных аккаунтов</div>
        )}
      </div>
    </div>
  );

  const renderTargetInput = () => (
    <div className="buy-modal__section">
      <p className="buy-modal__hint">
        Введите ID получателя (чат или канал), куда отправить подарок:
      </p>
      <Input
        ref={inputRef}
        value={targetId}
        onChange={(event) => setTargetId(event.target.value)}
        placeholder="Например, -1001234567890"
        error={inputError ?? undefined}
      />
      <div className="buy-modal__actions">
        <Button variant="secondary" onClick={() => setStep("accounts")}>Назад</Button>
        <Button onClick={handleSubmit}>Купить</Button>
      </div>
    </div>
  );

  const renderLoading = () => (
    <div className="buy-modal__centered">
      <div className="buy-modal__spinner" aria-hidden />
      <p className="buy-modal__hint">Загружается…</p>
    </div>
  );

  const renderResult = () => (
    <div className="buy-modal__centered">
      <div
        className={resultOk ? "buy-modal__status buy-modal__status--success" : "buy-modal__status buy-modal__status--error"}
      >
        {resultOk ? "✅" : "❌"}
      </div>
      <p className="buy-modal__result-message">{resultMessage}</p>
      <Button variant="secondary" onClick={onClose}>
        Вернуться к подаркам
      </Button>
    </div>
  );

  const modalTitle = gift
    ? `Покупка подарка #${gift.id} — ${gift.title || dateFormatter.format(new Date())}`
    : "Покупка подарка";

  return (
    <Modal open={open} onClose={onClose} title={modalTitle}>
      <div className="buy-modal">
        {gift && (
          <div className="buy-modal__meta">
            <span className="buy-modal__meta-item">Цена: {gift.price.toLocaleString("ru-RU")}⭐</span>
            {gift.isLimited && (
              <span className="buy-modal__meta-item">
                Доступно: {(gift.availableAmount ?? gift.perUserAvailable ?? 0).toLocaleString("ru-RU")}
              </span>
            )}
          </div>
        )}
        {step === "accounts" && renderAccounts()}
        {step === "target" && renderTargetInput()}
        {step === "loading" && renderLoading()}
        {step === "result" && renderResult()}
      </div>
    </Modal>
  );
};

