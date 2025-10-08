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
import { createApiProfile } from "../../entities/accounts/apiProfiles";
import type { HttpError } from "../../shared/api/httpClient";
import { showError, showInfo, showSuccess } from "../../shared/ui/feedback/toast";

const schema = z.object({
  name: z.string().optional(),
  apiId: z.string().min(1, "Введите API ID"),
  apiHash: z.string().min(10, "Введите API HASH"),
});

export type AddApiProfileModalValues = z.infer<typeof schema>;

export interface AddApiProfileModalProps {
  open: boolean;
  onClose: () => void;
  onSaved: (apiProfileId: number) => void;
}

export const AddApiProfileModal: React.FC<AddApiProfileModalProps> = ({ open, onClose, onSaved }) => {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<AddApiProfileModalValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", apiId: "", apiHash: "" },
  });

  const extractExistingProfileId = (error: unknown): number | undefined => {
    if (typeof error !== "object" || error === null) {
      return undefined;
    }
    const httpError = error as Partial<HttpError>;
    const payload = httpError.payload;
    if (typeof payload !== "object" || payload === null) {
      return undefined;
    }
    const maybePayload = payload as {
      error?: unknown;
      existing_id?: unknown;
    };
    const isDuplicateError =
      maybePayload.error === "duplicate_api_id" || maybePayload.error === "duplicate_api_hash";
    if (!isDuplicateError) {
      return undefined;
    }
    return typeof maybePayload.existing_id === "number" ? maybePayload.existing_id : undefined;
  };

  const onSubmit = handleSubmit(async (values) => {
    try {
      const apiIdNumber = Number.parseInt(values.apiId, 10);
      if (Number.isNaN(apiIdNumber)) {
        showError({ error: "API ID должен быть числом" });
        return;
      }
      const created = await createApiProfile({
        api_id: apiIdNumber,
        api_hash: values.apiHash,
        name: values.name ?? "",
      });
      showSuccess("API сохранён");
      onSaved(created.id);
      onClose();
    } catch (error: unknown) {
      const existingId = extractExistingProfileId(error);
      if (typeof existingId === "number") {
        showInfo("Такой API уже есть — используем его");
        onSaved(existingId);
        onClose();
        return;
      }
      showError(error, "Не удалось сохранить API");
    }
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="API ID / API HASH"
      footer={
        <Button type="submit" form="add-api-form" loading={isSubmitting} disabled={isSubmitting}>
          Сохранить
        </Button>
      }
    >
      <form id="add-api-form" onSubmit={onSubmit} className="modal-form" noValidate>
        <FormField label="Название" description="Отображается только в панели">
          <Input placeholder="Опционально" {...register("name")} />
        </FormField>
        <FormField label="API ID" error={errors.apiId?.message} required>
          <Input placeholder="Например, 123456" {...register("apiId")} />
        </FormField>
        <FormField label="API HASH" error={errors.apiHash?.message} required>
          <Input placeholder="Секретный ключ" {...register("apiHash")} />
        </FormField>
      </form>
    </Modal>
  );
};
