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

const schema = z.object({
  channelId: z.string().optional(),
  title: z.string().optional(),
  priceMin: z
    .string()
    .optional()
    .transform((value) => (value ? Number(value) : null))
    .refine((value) => value === null || value >= 0, "Цена не может быть отрицательной"),
  priceMax: z
    .string()
    .optional()
    .transform((value) => (value ? Number(value) : null))
    .refine((value) => value === null || value >= 0, "Цена не может быть отрицательной"),
  supplyMin: z
    .string()
    .optional()
    .transform((value) => (value ? Number(value) : null))
    .refine((value) => value === null || value >= 0, "Supply не может быть отрицательным"),
  supplyMax: z
    .string()
    .optional()
    .transform((value) => (value ? Number(value) : null))
    .refine((value) => value === null || value >= 0, "Supply не может быть отрицательным"),
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
      showError({ error: "Укажи ID канала" });
      return;
    }
    if (priceMin !== null && priceMax !== null && priceMin > priceMax) {
      showError({ error: "price_min ≤ price_max" });
      return;
    }
    if (supplyMin !== null && supplyMax !== null && supplyMin > supplyMax) {
      showError({ error: "supply_min ≤ supply_max" });
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
        await showPromise(promise, "Сохраняю…", "Сохранено", "Ошибка сохранения");
      } else {
        const promise = createChannel({
          channelId: channelId!,
          title: payload.title ?? null,
          priceMin: payload.priceMin,
          priceMax: payload.priceMax,
          supplyMin: payload.supplyMin,
          supplyMax: payload.supplyMax,
        });
        await showPromise(promise, "Соединяюсь…", "Канал добавлен", "Не удалось добавить канал");
      }
      onSaved();
      onClose();
    } catch (error) {
      showError(error, "Не удалось сохранить канал");
    }
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEdit ? "Канал" : "Добавить канал"}
      footer={
        <Button type="submit" form="edit-channel-form" loading={isSubmitting} disabled={isSubmitting}>
          Сохранить
        </Button>
      }
    >
      <form id="edit-channel-form" onSubmit={onSubmit} className="modal-form" noValidate>
        {!isEdit && (
          <FormField label="ID канала" error={errors.channelId?.message ?? undefined} required>
            <Input placeholder="-1001234567890" {...register("channelId", { required: !isEdit })} />
          </FormField>
        )}
        <FormField label="Название" description="Опционально">
          <Input placeholder="Название" {...register("title")} />
        </FormField>
        <div className="two-column-grid">
          <FormField label="Цена мин">
            <Input
              type="number"
              min={0}
              {...register("priceMin", { setValueAs: (value) => (value === "" ? null : Number(value)) })}
            />
          </FormField>
          <FormField label="Цена макс">
            <Input
              type="number"
              min={0}
              {...register("priceMax", { setValueAs: (value) => (value === "" ? null : Number(value)) })}
            />
          </FormField>
        </div>
        <div className="two-column-grid">
          <FormField label="Supply мин">
            <Input
              type="number"
              min={0}
              {...register("supplyMin", { setValueAs: (value) => (value === "" ? null : Number(value)) })}
            />
          </FormField>
          <FormField label="Supply макс">
            <Input
              type="number"
              min={0}
              {...register("supplyMax", { setValueAs: (value) => (value === "" ? null : Number(value)) })}
            />
          </FormField>
        </div>
      </form>
    </Modal>
  );
};
