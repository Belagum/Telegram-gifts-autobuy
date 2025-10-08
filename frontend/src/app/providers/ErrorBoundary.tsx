// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { showError } from "../../shared/ui/feedback/toast";

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends React.Component<React.PropsWithChildren, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    console.error("Unhandled error", error);
    showError(error, "Непредвиденная ошибка интерфейса");
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: "var(--spacing-xl)" }}>
          <h1>Что-то пошло не так</h1>
          <p>Мы уже знаем о проблеме. Попробуйте обновить страницу.</p>
        </div>
      );
    }
    return this.props.children;
  }
}
