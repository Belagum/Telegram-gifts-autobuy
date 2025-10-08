// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

export interface SseOptions<T> {
  path: string;
  event?: string;
  onEvent: (payload: T) => void;
  onError?: (error: Event) => void;
}

export const createSseStream = <T>({ path, event = "message", onEvent, onError }: SseOptions<T>) => {
  const source = new EventSource(path, { withCredentials: true });
  const handler = (evt: MessageEvent) => {
    try {
      const parsed = JSON.parse(evt.data) as T;
      onEvent(parsed);
    } catch (error) {
      console.warn("Failed to parse SSE payload", error);
    }
  };
  source.addEventListener(event, handler);
  if (onError) {
    source.onerror = onError;
  }
  return () => {
    source.removeEventListener(event, handler);
    source.close();
  };
};
