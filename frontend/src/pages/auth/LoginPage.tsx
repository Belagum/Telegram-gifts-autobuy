// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { Link } from "react-router-dom";
import { LoginForm } from "../../features/auth/LoginForm";
import "./auth.css";

export const LoginPage: React.FC = () => {
  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Вход</h1>
        <LoginForm />
        <div className="auth-card__footer">
          Нет аккаунта? <Link to="/register">Зарегистрируйтесь</Link>
        </div>
      </div>
    </div>
  );
};
