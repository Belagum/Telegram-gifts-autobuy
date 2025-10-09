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
  channelId: z.string().optional(),
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
  const formRef = React.useRef<HTMLFormElement | null>(null);
  const defaultValues: EditChannelFormValues = React.useMemo(
    () => ({
      channelId: initial?.channelId ?? "",
      title: initial?.title ?? "",
      priceMin: initial?.priceMin ?? null,
      priceMax: initial?.priceMax ?? null,
      supplyMin: initial?.supplyMin ?? null,
      supplyMax: initial?.supplyMax ?? null,
    }),
    [initial],
  );

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<EditChannelFormValues>({
    resolver: zodResolver(schema),
    defaultValues,
  });

  React.useEffect(() => {
    reset(defaultValues);
  }, [defaultValues, reset]);

  const onSubmit = handleSubmit(async (values) => {
    const { channelId, title, priceMin, priceMax, supplyMin, supplyMax } = values;
    if (!isEdit && !channelId) {
      showError({ error: "Введите ID канала" });
      return;
    }
    if (priceMin !== null && priceMax !== null && priceMin > priceMax) {
      showError({ error: "Минимальная цена больше максимальной" });
      return;
    }
    if (supplyMin !== null && supplyMax !== null && supplyMin > supplyMax) {
      showError({ error: "Минимальный supply больше максимального" });
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
        const promise = updateChannel(initial.id, payload);
        await showPromise(
          promise,
          "Сохраняю изменения…",
          "Сохранено",
          (err) =>
            (err as any)?.payload?.detail ||
            (err as any)?.payload?.error ||
            "Не удалось сохранить изменения",
        );
      } else {
        const promise = createChannel({
          channelId: channelId!,
          title: payload.title ?? null,
          priceMin: payload.priceMin,
          priceMax: payload.priceMax,
          supplyMin: payload.supplyMin,
          supplyMax: payload.supplyMax,
        });
        await showPromise(
          promise,
          "Добавляю канал…",
          "Канал добавлен",
          (err) =>
            (err as any)?.payload?.detail ||
            (err as any)?.payload?.error ||
            "Не удалось добавить канал",
        );
      }
      onSaved();
      onClose();
    } catch {
    }
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEdit ? "Редактирование канала" : "Добавление канала"}
      footer={
        <Button type="submit" form="edit-channel-form" onClick={() => onSubmit()} loading={isSubmitting} disabled={isSubmitting}>
          Сохранить
        </Button>
      }
    >
      <form id="edit-channel-form" ref={formRef} onSubmit={onSubmit} className="modal-form" noValidate>
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
