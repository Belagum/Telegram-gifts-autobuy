// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { Outlet } from "react-router-dom";
import { AppLayout } from "../../shared/ui/layout/AppLayout";

export const PrivateLayout: React.FC = () => {
  return (
    <AppLayout>
      <Outlet />
    </AppLayout>
  );
};
