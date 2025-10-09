// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null;
};

const readStringProperty = (source: Record<string, unknown>, key: string): string | undefined => {
  const candidate = source[key];
  return typeof candidate === "string" ? candidate : undefined;
};

export const extractApiErrorMessage = (error: unknown, fallback: string): string => {
  if (typeof error === "string") {
    return error;
  }
  if (!isRecord(error)) {
    return fallback;
  }

  const directMessage = readStringProperty(error, "detail") ?? readStringProperty(error, "error");
  if (directMessage) {
    return directMessage;
  }

  const payloadCandidate = (error as Record<string, unknown> & { payload?: unknown }).payload;
  if (isRecord(payloadCandidate)) {
    return (
      readStringProperty(payloadCandidate, "detail") ??
      readStringProperty(payloadCandidate, "error") ??
      fallback
    );
  }

  return fallback;
};

