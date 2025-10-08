// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { me } from "../features/auth/api";
import { onUnauthorized } from "../shared/api/httpClient";
import type { HttpError } from "../shared/api/httpClient";
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
        if (cancelled) {
          return;
        }

        const httpError = error as Partial<HttpError>;
        const status = typeof httpError?.status === "number" ? httpError.status : undefined;
        const isUnauthorized = Boolean(httpError?.isUnauthorized || status === 401);
        const isEndpointMissing = status === 404;
        const isNetworkError = error instanceof TypeError;
        const shouldRedirectToLogin = !isPublic && (isUnauthorized || isEndpointMissing || isNetworkError);

        if (shouldRedirectToLogin) {
          const fallbackMessage = isUnauthorized
            ? "Требуется авторизация"
            : isEndpointMissing
              ? "Сервер авторизации недоступен"
              : "Не удалось связаться с сервером";
          showError(error, fallbackMessage);
          navigate("/login", { replace: true });
        } else if (!isPublic) {
          showError(error, "Не удалось загрузить профиль");
        } else if (isPublic && (isEndpointMissing || isNetworkError)) {
          showError(error, "Сервер авторизации недоступен");
        }

        setReady(true);
      } finally {
        pendingRef.current = false;
      }
    })();

    return () => {
      cancelled = true;
      // Ensure StrictMode re-run doesn't get blocked by the pending flag
      // so the second effect execution can proceed normally.
      pendingRef.current = false;
    };
  }, [location.pathname, navigate]);

  if (!ready) {
    return null;
  }

  return <Outlet />;
};
