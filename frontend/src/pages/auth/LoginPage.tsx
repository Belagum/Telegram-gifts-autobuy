// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { Link } from "react-router-dom";
import { LoginForm } from "../../features/auth/LoginForm";
import { useUiStore } from "../../app/store/uiStore";
import { AuthWelcome } from "./AuthWelcome";
import "./auth.css";

export const LoginPage: React.FC = () => {
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
              <h2 className="auth-card__title">Вход</h2>
              <p className="auth-card__subtitle">Добро пожаловать! Пожалуйста, войдите в свой аккаунт.</p>
            </div>
            <LoginForm />
            <div className="auth-card__footer">
              Нет аккаунта? <Link to="/register">Зарегистрируйтесь</Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
