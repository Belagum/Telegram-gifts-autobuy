// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { Link } from "react-router-dom";
import { RegisterForm } from "../../features/auth/RegisterForm";
import { useUiStore } from "../../app/store/uiStore";
import { AuthWelcome } from "./AuthWelcome";
import "./auth.css";

export const RegisterPage: React.FC = () => {
  const { theme, toggleTheme } = useUiStore();

  return (
    <div className="auth-page">
      <button
        onClick={toggleTheme}
        className="theme-toggle"
        title={`Переключить на ${theme === "light" ? "темную" : "светлую"} тему`}
      >
        {theme === "light" ? "🌙" : "☀️"}
      </button>
      <div className="auth-container">
        <AuthWelcome />
        <div className="auth-form-panel">
          <div className="auth-card">
            <div className="auth-card__header">
              <h2 className="auth-card__title">Регистрация</h2>
              <p className="auth-card__subtitle">Создайте новый аккаунт для начала работы.</p>
            </div>
            <RegisterForm />
            <div className="auth-card__footer">
              Уже есть аккаунт? <Link to="/login">Войти</Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
