// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import DOMPurify from "dompurify";
import { useUiStore } from "../../app/store/uiStore";

export interface HttpError extends Error {
  status: number;
  payload?: unknown;
  isUnauthorized?: boolean;
}

export type HttpMethod = "GET" | "POST" | "PATCH" | "DELETE";

export interface HttpClientOptions {
  method?: HttpMethod;
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  parseJson?: boolean;
  asNdjson?: boolean;
  timeout?: number;
}

/** default timeout*/
const DEFAULT_TIMEOUT_MS = 30000;

const unauthorizedEvent = new EventTarget();

const createHttpError = (message: string, status: number, payload?: unknown): HttpError => {
  const error = new Error(message) as HttpError;
  error.status = status;
  if (payload !== undefined) {
    error.payload = payload;
  }
  return error;
};

export const onUnauthorized = (handler: () => void) => {
  const listener = () => handler();
  unauthorizedEvent.addEventListener("unauthorized", listener);
  return () => unauthorizedEvent.removeEventListener("unauthorized", listener);
};

export const readCsrfToken = () => {
  if (typeof document === "undefined") {
    return "";
  }
  const meta = document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]');
  return meta?.content ?? "";
};

const sanitizeBody = (data: unknown) => {
  if (typeof data === "string") {
    return DOMPurify.sanitize(data);
  }
  return data;
};

const baseUrl = "/api";

export const httpClient = async <TResponse>(
  path: string,
  { method = "GET", body, headers = {}, signal, parseJson = true, timeout = DEFAULT_TIMEOUT_MS }: HttpClientOptions = {},
): Promise<TResponse> => {
  const localController = new AbortController();
  let timeoutId: ReturnType<typeof setTimeout> | undefined;

  if (!signal && timeout > 0) {
    timeoutId = setTimeout(() => localController.abort(), timeout);
  }

  const abortSignal = signal ?? localController.signal;

  const finalHeaders: Record<string, string> = {
    Accept: "application/json",
    ...headers,
  };

  const csrfToken = readCsrfToken();
  if (csrfToken) {
    finalHeaders["X-CSRF-Token"] = csrfToken;
  }

  let requestBody: BodyInit | undefined;
  if (body instanceof FormData) {
    requestBody = body;
  } else if (body !== undefined) {
    finalHeaders["Content-Type"] = "application/json";
    requestBody = JSON.stringify(body);
  }

  useUiStore.getState().setGlobalLoading(true);

  try {
    const response = await fetch(`${baseUrl}${path}`, {
      credentials: "include",
      method,
      headers: finalHeaders,
      body: requestBody,
      signal: abortSignal,
      mode: "cors",
    });

    const contentType = response.headers.get("content-type") ?? "";
    const isJson = contentType.includes("application/json");

    if (response.status === 401) {
      const payload = isJson ? await response.json().catch(() => undefined) : undefined;
      const error = createHttpError("Unauthorized", response.status, payload);
      error.isUnauthorized = true;
      unauthorizedEvent.dispatchEvent(new Event("unauthorized"));
      throw error;
    }

    if (!response.ok) {
      const errorBody = isJson ? await response.json().catch(() => undefined) : undefined;
      const error = createHttpError("Request failed", response.status, errorBody);
      throw error;
    }

    if (!parseJson) {
      return undefined as TResponse;
    }

    if (isJson) {
      return (await response.json()) as TResponse;
    }

    const text = await response.text();
    return sanitizeBody(text) as TResponse;
  } catch (error) {
    if ((error as Error)?.name === "AbortError") {
      throw error;
    }
    if (import.meta.env.DEV) {
      console.error("HTTP error", error);
    }
    throw error;
  } finally {
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId);
    }
    useUiStore.getState().setGlobalLoading(false);
  }
};

export interface NdjsonStreamOptions<T> {
  path: string;
  method?: HttpMethod;
  body?: unknown;
  onEvent: (data: T) => void;
  onError?: (error: Error) => void;
}

export const streamNdjson = async <T>({ path, method = "POST", body, onEvent, onError }: NdjsonStreamOptions<T>) => {
  const headers: Record<string, string> = {
    Accept: "application/x-ndjson",
  };
  const csrfToken = readCsrfToken();
  if (csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers,
    credentials: "include",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const error = new Error(`Stream request failed with status ${response.status}`);
    onError?.(error);
    throw error;
  }

  if (!response.body) {
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      let index = buffer.indexOf("\n");
      while (index >= 0) {
        const chunk = buffer.slice(0, index).trim();
        buffer = buffer.slice(index + 1);
        if (chunk) {
          try {
            onEvent(JSON.parse(chunk) as T);
          } catch (parseError) {
            if (import.meta.env.DEV) {
              console.warn("Failed to parse NDJSON chunk", parseError);
            }
          }
        }
        index = buffer.indexOf("\n");
      }
    }
  } finally {
    reader.releaseLock();
  }
};
