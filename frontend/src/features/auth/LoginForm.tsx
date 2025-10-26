// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "../../shared/ui/button/Button";
import { Input } from "../../shared/ui/input/Input";
import { login } from "./api";
import { showError, showSuccess } from "../../shared/ui/feedback/toast";
import { useNavigate } from "react-router-dom";

const loginSchema = z.object({
  username: z.string().min(3, "Введите логин"),
  password: z.string().min(6, "Минимум 6 символов"),
  rememberMe: z.boolean().optional(),
});

export type LoginFormValues = z.infer<typeof loginSchema>;

export const LoginForm: React.FC = () => {
  const navigate = useNavigate();
  const usernameId = React.useId();
  const passwordId = React.useId();
  const {
    handleSubmit,
    register,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { username: "", password: "", rememberMe: false },
  });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await login({
        username: values.username,
        password: values.password,
        rememberMe: values.rememberMe,
      });
      showSuccess("Вход выполнен");
      navigate("/", { replace: true });
    } catch (error) {
      showError(error, "Неверные данные");
    }
  });

  return (
    <form className="auth-form" onSubmit={onSubmit} noValidate>
      <div>
        <label className="auth-form__label" htmlFor={usernameId}>
          Логин
        </label>
        <Input
          id={usernameId}
          placeholder="username"
          autoComplete="username"
          {...register("username")}
        />
        {errors.username && <div className="ui-input__error">{errors.username.message}</div>}
      </div>
      <div>
        <label className="auth-form__label" htmlFor={passwordId}>
          Пароль
        </label>
        <Input
          id={passwordId}
          type="password"
          placeholder="••••••••"
          autoComplete="current-password"
          {...register("password")}
        />
        {errors.password && <div className="ui-input__error">{errors.password.message}</div>}
      </div>
      <div className="auth-form__extras">
        <label className="auth-checkbox">
          <input
            type="checkbox"
            className="auth-checkbox__input"
            {...register("rememberMe")}
          />
          <span className="auth-checkbox__label">Запомнить меня</span>
        </label>
        <button type="button" className="auth-link">
          Забыли пароль?
        </button>
      </div>
      <Button type="submit" loading={isSubmitting} disabled={isSubmitting}>
        {isSubmitting ? "Загрузка…" : "Войти"}
      </Button>
    </form>
  );
};
