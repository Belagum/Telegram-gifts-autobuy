// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import clsx from "clsx";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { FormField } from "../../shared/ui/form-field/FormField";
import { Input } from "../../shared/ui/input/Input";
import { Button } from "../../shared/ui/button/Button";
import { getSettings, setSettings } from "../../entities/settings/api";
import type { Settings } from "../../entities/settings/model";
import { showError, showSuccess } from "../../shared/ui/feedback/toast";
import "./settings.css";
import { usePopupAutoSize } from "../../shared/lib/hooks/usePopupAutoSize";

const schema = z.object({
  botToken: z.string().optional(),
  notifyChatTail: z
    .string()
    .optional()
    .transform((value) => (value ? value.replace(/\D+/g, "") : "")),
  buyTargetId: z
    .string()
    .optional()
    .refine((value) => !value || /^-?\d+$/.test(value), "ID должен содержать только цифры"),
});

export type SettingsFormValues = z.infer<typeof schema>;

const transformSettingsToForm = (settings: Settings): SettingsFormValues => {
  const chatIdRaw = settings.notifyChatId;
  const chatId = chatIdRaw == null ? "" : String(chatIdRaw);
  return {
    botToken: settings.botToken ?? "",
    notifyChatTail: chatId.startsWith("-100") ? chatId.slice(4) : chatId.replace(/\D+/g, ""),
    buyTargetId: settings.buyTargetId ? String(settings.buyTargetId) : "",
  };
};

export const SettingsPage: React.FC = () => {
  const [isPopup, setIsPopup] = React.useState(false);
  React.useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const flag = params.get("popup");
    setIsPopup(Boolean((window as Window).opener || flag));
  }, []);

  usePopupAutoSize(isPopup);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<SettingsFormValues>({
    resolver: zodResolver(schema),
    defaultValues: { botToken: "", notifyChatTail: "", buyTargetId: "" },
  });

  React.useEffect(() => {
    (async () => {
      try {
        const settings = await getSettings();
        reset(transformSettingsToForm(settings));
      } catch (error) {
        showError(error, "Не удалось загрузить настройки");
      }
    })();
  }, [reset]);

  const onSubmit = handleSubmit(async (values) => {
    const payload: Settings = {
      botToken: values.botToken?.trim() || null,
      notifyChatId: values.notifyChatTail ? `-100${values.notifyChatTail}` : null,
      buyTargetId: values.buyTargetId?.trim() ? values.buyTargetId.trim() : null,
    };
    try {
      await setSettings(payload);
      showSuccess("Настройки сохранены");
      window.close();
    } catch (error) {
      showError(error, "Не удалось сохранить настройки");
    }
  });

  return (
    <div className={clsx("settings-page", { "is-popup": isPopup })}>
      <header className="settings-header">
        <h1>Настройки</h1>
      </header>
      <form className="settings-form" onSubmit={onSubmit} noValidate>
        <FormField label="Bot token" description="Используется для уведомлений и предпросмотра." error={errors.botToken?.message}>
          <Input type="password" placeholder="123456:ABCDEF" {...register("botToken")} />
        </FormField>
        <FormField
          label="ID чата для уведомлений"
          description="Можно вставить полный ID — префикс -100 добавится автоматически."
          error={errors.notifyChatTail?.message}
        >
          <div className="chat-input">
            <span className="chat-input__prefix">-100</span>
            <Input {...register("notifyChatTail")} inputMode="numeric" placeholder="XXXXXXXXXXXX" />
          </div>
        </FormField>
        <FormField
          label="ID получателя покупок (опционально)"
          description="Если заполнено — покупки отправляются на этот ID. Пусто — по каналам из списка."
          error={errors.buyTargetId?.message}
        >
          <Input {...register("buyTargetId")} inputMode="numeric" placeholder="Например, -1001234567890" />
        </FormField>
        <div className="settings-footer">
          <Button type="submit" loading={isSubmitting} disabled={isSubmitting}>
            {isSubmitting ? "Сохраняю…" : "Сохранить"}
          </Button>
        </div>
      </form>
    </div>
  );
};
