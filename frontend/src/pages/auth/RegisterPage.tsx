// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { Link } from "react-router-dom";
import { RegisterForm } from "../../features/auth/RegisterForm";
import "./auth.css";

export const RegisterPage: React.FC = () => {
  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Регистрация</h1>
        <RegisterForm />
        <div className="auth-card__footer">
          Уже есть аккаунт? <Link to="/login">Войти</Link>
        </div>
      </div>
    </div>
  );
};
