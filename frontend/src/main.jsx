// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import GiftsPage from "./pages/GiftsPage.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";
import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import App from "./App.jsx";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import "./styles.css";
import { ModalProvider } from "./ui/ModalStack.jsx";

createRoot(document.getElementById("root")).render(
  <ModalProvider>
    <BrowserRouter>
      <ToastContainer position="top-right" theme="dark" newestOnTop closeOnClick pauseOnHover />
      <Routes>
        <Route element={<App />}>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/" element={<Dashboard />} />
          <Route path="/gifts" element={<GiftsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </ModalProvider>
);
