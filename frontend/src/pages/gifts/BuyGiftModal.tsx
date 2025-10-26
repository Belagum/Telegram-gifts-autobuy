// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { Modal } from "../../shared/ui/modal/Modal";
import { Button } from "../../shared/ui/button/Button";
import { Input } from "../../shared/ui/input/Input";
import type { Gift } from "../../entities/gifts/model";
import type { Account } from "../../entities/accounts/model";
import { buyGift } from "../../entities/gifts/api";
import { extractApiErrorMessage } from "../../shared/api/errorMessages";
import { resolveErrorMessage, resolveSuccessMessage } from "../../shared/api/messages";

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

  React.useEffect(() => {
    if (step !== "result") return;

    const handleResultKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Enter") {
        event.preventDefault();
        onClose();
      }
    };

    document.addEventListener("keydown", handleResultKeyDown);
    return () => {
      document.removeEventListener("keydown", handleResultKeyDown);
    };
  }, [step, onClose]);

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
        const message = resolveErrorMessage(
          response.error,
          response.errorCode,
          response.context ?? undefined,
          "Не удалось купить подарок",
        );
        throw new Error(message);
      }
      setResultOk(true);
      setResultMessage(
        resolveSuccessMessage(response.result, response.context ?? undefined, "Подарок успешно куплен"),
      );
      setStep("result");
      await onPurchased?.();
    } catch (error) {
      setResultOk(false);
      setResultMessage(extractApiErrorMessage(error, "Не удалось купить подарок"));
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
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            handleSubmit();
          }
        }}
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
      <div className="buy-modal__status-container">
        <svg
          className={resultOk ? "buy-modal__status buy-modal__status--success" : "buy-modal__status buy-modal__status--error"}
          viewBox="0 0 52 52"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle
            className="buy-modal__status-circle"
            cx="26"
            cy="26"
            r="25"
            fill="none"
          />
          {resultOk ? (
            <path
              className="buy-modal__status-check"
              fill="none"
              d="M14.1 27.2l7.1 7.2 16.7-16.8"
            />
          ) : (
            <>
              <path
                className="buy-modal__status-cross"
                fill="none"
                d="M16 16 l20 20"
              />
              <path
                className="buy-modal__status-cross"
                fill="none"
                d="M36 16 l-20 20"
              />
            </>
          )}
        </svg>
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

