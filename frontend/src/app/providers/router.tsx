// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import { App } from "../App";
import { PrivateLayout } from "./PrivateLayout";
import { LoginPage } from "../../pages/auth/LoginPage";
import { RegisterPage } from "../../pages/auth/RegisterPage";
import { DashboardPage } from "../../pages/dashboard/DashboardPage";
import { GiftsPage } from "../../pages/gifts/GiftsPage";
import { SettingsPage } from "../../pages/settings/SettingsPage";
import { AdminPage } from "../../pages/admin/AdminPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      {
        element: <PrivateLayout />,
        children: [
          { index: true, element: <DashboardPage /> },
          { path: "gifts", element: <GiftsPage /> },
          { path: "settings", element: <SettingsPage /> },
          { path: "admin", element: <AdminPage /> },
        ],
      },
      { path: "login", element: <LoginPage /> },
      { path: "register", element: <RegisterPage /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
