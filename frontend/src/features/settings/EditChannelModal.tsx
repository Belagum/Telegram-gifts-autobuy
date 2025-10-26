// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Modal } from "../../shared/ui/modal/Modal";
import { FormField } from "../../shared/ui/form-field/FormField";
import { Input } from "../../shared/ui/input/Input";
import { Button } from "../../shared/ui/button/Button";
import { createChannel, updateChannel } from "../../entities/settings/api";
import type { Channel } from "../../entities/settings/channel";
import { extractApiErrorMessage } from "../../shared/api/errorMessages";
import { showError, showPromise } from "../../shared/ui/feedback/toast";

const numericNullable = z.preprocess(
  (value) => {
    if (value === "" || value == null) return null;
    if (typeof value === "string") return Number(value);
    if (typeof value === "number") return value;
    return null;
  },
  z.number().nonnegative().nullable(),
);

const schema = z.object({
  channelId: z.preprocess(
    (value) => {
      if (value === "" || value == null) return undefined;
      return String(value);
    },
    z.string().optional(),
  ),
  title: z.string().optional(),
  priceMin: numericNullable,
  priceMax: numericNullable,
  supplyMin: numericNullable,
  supplyMax: numericNullable,
});

export type EditChannelFormValues = z.infer<typeof schema>;

export interface EditChannelModalProps {
  open: boolean;
  initial?: Channel | null;
  onClose: () => void;
  onSaved: () => void;
}

export const EditChannelModal: React.FC<EditChannelModalProps> = ({ open, initial, onClose, onSaved }) => {
  const isEdit = Boolean(initial?.id);
  const formRef = React.useRef<HTMLFormElement>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<EditChannelFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      channelId: initial?.channelId ?? "",
      title: initial?.title ?? "",
      priceMin: initial?.priceMin ?? null,
      priceMax: initial?.priceMax ?? null,
      supplyMin: initial?.supplyMin ?? null,
      supplyMax: initial?.supplyMax ?? null,
    },
  });

  React.useEffect(() => {
    if (!open) return;
    if (initial && initial.id) {
      reset({
        channelId: initial.channelId ?? "",
        title: initial.title ?? "",
        priceMin: initial.priceMin ?? null,
        priceMax: initial.priceMax ?? null,
        supplyMin: initial.supplyMin ?? null,
        supplyMax: initial.supplyMax ?? null,
      });
    } else {
      reset({
        channelId: "",
        title: "",
        priceMin: null,
        priceMax: null,
        supplyMin: null,
        supplyMax: null,
      });
    }
  }, [open, initial, reset]);

  const onSubmit = handleSubmit(
    async (values) => {
      const { channelId, title, priceMin, priceMax, supplyMin, supplyMax } = values;
      if (!isEdit && !channelId) {
        showError("Введите ID канала");
        return;
      }
      if (priceMin !== null && priceMax !== null && priceMin > priceMax) {
        showError("Минимальная цена больше максимальной");
        return;
      }
      if (supplyMin !== null && supplyMax !== null && supplyMin > supplyMax) {
        showError("Минимальный supply больше максимального");
        return;
      }

      const payload: Partial<Pick<Channel, "title" | "priceMin" | "priceMax" | "supplyMin" | "supplyMax">> = {
        title: title?.trim() || null,
        priceMin,
        priceMax,
        supplyMin,
        supplyMax,
      };

      try {
        if (isEdit && initial) {
          const diff: Partial<Channel> = {};
          if ((payload.title ?? null) !== (initial.title ?? null)) diff.title = payload.title ?? null;
          if (payload.priceMin !== initial.priceMin) diff.priceMin = payload.priceMin ?? null;
          if (payload.priceMax !== initial.priceMax) diff.priceMax = payload.priceMax ?? null;
          if (payload.supplyMin !== initial.supplyMin) diff.supplyMin = payload.supplyMin ?? null;
          if (payload.supplyMax !== initial.supplyMax) diff.supplyMax = payload.supplyMax ?? null;

          if (Object.keys(diff).length === 0) {
            showError("Нет изменений для сохранения");
            return;
          }

          await showPromise(
            updateChannel(initial.id, diff),
            "Сохраняю изменения…",
            "Сохранено",
            (err) => extractApiErrorMessage(err, "Не удалось сохранить изменения"),
          );
        } else {
          await showPromise(
            createChannel({
              channelId: channelId!,
              title: payload.title ?? null,
              priceMin: payload.priceMin,
              priceMax: payload.priceMax,
              supplyMin: payload.supplyMin,
              supplyMax: payload.supplyMax,
            }),
            "Добавляю канал…",
            "Канал добавлен",
            (err) => extractApiErrorMessage(err, "Не удалось добавить канал"),
          );
        }
        onSaved();
        onClose();
      } catch (error) {
        showError(error, "Не удалось сохранить изменения");
      }
    },
    () => {
      showError("Исправьте ошибки в форме");
    },
  );

  const handleSaveClick = () => {
    const formEl = formRef.current;
    if (!formEl) {
      showError("Форма недоступна");
      return;
    }
    if (typeof formEl.requestSubmit === "function") {
      formEl.requestSubmit();
      return;
    }
    const submitEvent = new Event("submit", { bubbles: true, cancelable: true });
    formEl.dispatchEvent(submitEvent);
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEdit ? "Редактирование канала" : "Добавление канала"}
      footer={
        <Button
          type="button"
          loading={isSubmitting}
          disabled={isSubmitting}
          onClick={handleSaveClick}
        >
          Сохранить
        </Button>
      }
    >
      <form 
        ref={formRef}
        id="edit-channel-form" 
        onSubmit={onSubmit}
        className="modal-form" 
        noValidate
      >
        {!isEdit && (
          <FormField label="ID канала" error={errors.channelId?.message ?? undefined} required>
            <Input placeholder="-1001234567890" {...register("channelId", { required: !isEdit })} />
          </FormField>
        )}
        <FormField label="Название" description="Необязательно">
          <Input placeholder="Название (опционально)" {...register("title")} />
        </FormField>
        <div className="two-column-grid">
          <FormField label="Цена от" error={errors.priceMin?.message ?? undefined}>
            <Input type="number" min={0} {...register("priceMin")} />
          </FormField>
          <FormField label="Цена до" error={errors.priceMax?.message ?? undefined}>
            <Input type="number" min={0} {...register("priceMax")} />
          </FormField>
        </div>
        <div className="two-column-grid">
          <FormField label="Supply от" error={errors.supplyMin?.message ?? undefined}>
            <Input type="number" min={0} {...register("supplyMin")} />
          </FormField>
          <FormField label="Supply до" error={errors.supplyMax?.message ?? undefined}>
            <Input type="number" min={0} {...register("supplyMax")} />
          </FormField>
        </div>
      </form>
    </Modal>
  );
};
