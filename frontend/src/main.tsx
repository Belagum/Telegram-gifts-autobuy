// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { router } from "./app/providers/router";
import { ErrorBoundary } from "./app/providers/ErrorBoundary";
import { initializeThemeDom } from "./app/store/uiStore";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import "./app/styles/global.css";

initializeThemeDom();

const container = document.getElementById("root");
if (!container) {
  throw new Error("Root container not found");
}

const root = ReactDOM.createRoot(container);
root.render(
  <React.StrictMode>
    <ErrorBoundary>
      <RouterProvider router={router} />
      <ToastContainer position="top-right" theme="dark" newestOnTop closeOnClick pauseOnHover />
    </ErrorBoundary>
  </React.StrictMode>,
);
