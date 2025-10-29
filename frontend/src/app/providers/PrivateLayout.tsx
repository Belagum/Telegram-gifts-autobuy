// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { Outlet, useLocation } from "react-router-dom";
import { AppLayout } from "../../shared/ui/layout/AppLayout";

export const PrivateLayout: React.FC = () => {
  const location = useLocation();

  const isSettingsRoute = location.pathname.endsWith("/settings");
  const isGiftsRoute = location.pathname.endsWith("/gifts");
  const isAdminRoute = location.pathname.endsWith("/admin");
  const searchParams = new URLSearchParams(location.search);
  const isPopup = Boolean((typeof window !== "undefined" && (window as Window).opener) || searchParams.get("popup"));

  if ((isSettingsRoute || isGiftsRoute || isAdminRoute) && isPopup) {
    return <Outlet />;
  }

  return (
    <AppLayout>
      <Outlet />
    </AppLayout>
  );
};
