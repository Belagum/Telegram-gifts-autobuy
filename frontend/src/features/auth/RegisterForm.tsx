// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "../../shared/ui/button/Button";
import { FormField } from "../../shared/ui/form-field/FormField";
import { Input } from "../../shared/ui/input/Input";
import { register as registerUser } from "./api";
import { showError, showSuccess } from "../../shared/ui/feedback/toast";
import { useNavigate } from "react-router-dom";

const registerSchema = z
  .object({
    username: z.string().min(3, "Введите логин"),
    password: z.string().min(6, "Минимум 6 символов"),
    confirmPassword: z.string().min(6, "Подтвердите пароль"),
  })
  .refine((data) => data.password === data.confirmPassword, {
    path: ["confirmPassword"],
    message: "Пароли не совпадают",
  });

export type RegisterFormValues = z.infer<typeof registerSchema>;

export const RegisterForm: React.FC = () => {
  const navigate = useNavigate();
  const {
    handleSubmit,
    register,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { username: "", password: "", confirmPassword: "" },
  });

  const onSubmit = handleSubmit(async ({ username, password }) => {
    try {
      await registerUser({ username, password });
      showSuccess("Регистрация выполнена");
      navigate("/", { replace: true });
    } catch (error) {
      showError(error, "Не удалось зарегистрироваться");
    }
  });

  return (
    <form className="auth-form" onSubmit={onSubmit} noValidate>
      <FormField label="Логин" error={errors.username?.message} required>
        <Input placeholder="username" autoComplete="username" {...register("username")} />
      </FormField>
      <FormField label="Пароль" error={errors.password?.message} required>
        <Input type="password" placeholder="password" {...register("password")} />
      </FormField>
      <FormField label="Подтверждение пароля" error={errors.confirmPassword?.message} required>
        <Input type="password" placeholder="repeat password" {...register("confirmPassword")} />
      </FormField>
      <Button type="submit" loading={isSubmitting} disabled={isSubmitting}>
        {isSubmitting ? "Загрузка…" : "Создать аккаунт"}
      </Button>
    </form>
  );
};
