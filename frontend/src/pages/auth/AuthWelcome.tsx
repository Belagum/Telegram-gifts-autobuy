// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";

export const AuthWelcome: React.FC = () => {
  return (
    <div className="auth-welcome">
      <div className="auth-welcome__content">
        <div className="auth-welcome__logo">🎁</div>
        <h1 className="auth-welcome__title">TG Gifts</h1>
        <p className="auth-welcome__subtitle">
          Управляйте подарками и аккаунтами Telegram в одном месте
        </p>
      </div>
    </div>
  );
};

