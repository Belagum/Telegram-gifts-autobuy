// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { me } from "../features/auth/api";
import { onUnauthorized } from "../shared/api/httpClient";
import { showError } from "../shared/ui/feedback/toast";

const PUBLIC_ROUTES = ["/login", "/register"];

export const App: React.FC = () => {
  const [ready, setReady] = React.useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const pendingRef = React.useRef(false);

  React.useEffect(() => {
    return onUnauthorized(() => {
      setReady(true);
      if (!PUBLIC_ROUTES.some((route) => location.pathname.startsWith(route))) {
        navigate("/login", { replace: true });
      }
    });
  }, [navigate, location.pathname]);

  React.useEffect(() => {
    let cancelled = false;
    const isPublic = PUBLIC_ROUTES.some((route) => location.pathname.startsWith(route));

    if (pendingRef.current) {
      return;
    }
    pendingRef.current = true;

    (async () => {
      try {
        await me();
        if (!cancelled) {
          setReady(true);
          if (isPublic) {
            navigate("/", { replace: true });
          }
        }
      } catch (error) {
        if (isPublic) {
          if (!cancelled) setReady(true);
        } else {
          if (!cancelled) {
            showError(error, "Требуется авторизация");
            navigate("/login", { replace: true });
          }
        }
      } finally {
        pendingRef.current = false;
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [location.pathname, navigate]);

  if (!ready) {
    return null;
  }

  return <Outlet />;
};
