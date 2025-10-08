// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "../../shared/ui/button/Button";
import { FormField } from "../../shared/ui/form-field/FormField";
import { Input } from "../../shared/ui/input/Input";
import { login } from "./api";
import { showError, showSuccess } from "../../shared/ui/feedback/toast";
import { useNavigate } from "react-router-dom";

const loginSchema = z.object({
  username: z.string().min(3, "Введите логин"),
  password: z.string().min(6, "Минимум 6 символов"),
});

export type LoginFormValues = z.infer<typeof loginSchema>;

export const LoginForm: React.FC = () => {
  const navigate = useNavigate();
  const {
    handleSubmit,
    register,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { username: "", password: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await login(values);
      showSuccess("Вход выполнен");
      navigate("/", { replace: true });
    } catch (error) {
      showError(error, "Неверные данные");
    }
  });

  return (
    <form className="auth-form" onSubmit={onSubmit} noValidate>
      <FormField label="Логин" error={errors.username?.message} required>
        <Input placeholder="username" autoComplete="username" {...register("username")} />
      </FormField>
      <FormField label="Пароль" error={errors.password?.message} required>
        <Input
          type="password"
          placeholder="password"
          autoComplete="current-password"
          {...register("password")}
        />
      </FormField>
      <Button type="submit" loading={isSubmitting} disabled={isSubmitting}>
        {isSubmitting ? "Загрузка…" : "Войти"}
      </Button>
    </form>
  );
};
