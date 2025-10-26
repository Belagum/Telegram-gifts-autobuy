// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import { resolveErrorMessage } from "./messages";

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null;
};

const readStringProperty = (source: Record<string, unknown>, key: string): string | undefined => {
  const candidate = source[key];
  return typeof candidate === "string" ? candidate : undefined;
};

const readRecordProperty = (source: Record<string, unknown>, key: string) => {
  const candidate = source[key];
  return isRecord(candidate) ? candidate : undefined;
};

const resolveFromSource = (
  source: Record<string, unknown>,
  fallback: string,
): string | undefined => {
  const detail = readStringProperty(source, "detail");
  if (detail) {
    return detail;
  }
  const message = readStringProperty(source, "message");
  if (message) {
    return message;
  }
  const errorCode = readStringProperty(source, "error_code");
  const errorValue = readStringProperty(source, "error");
  const context = readRecordProperty(source, "context");
  if (errorValue || errorCode) {
    return resolveErrorMessage(errorValue, errorCode, context, fallback);
  }
  return undefined;
};

export const extractApiErrorMessage = (error: unknown, fallback: string): string => {
  if (typeof error === "string") {
    return error;
  }

  if (isRecord(error)) {
    const direct = resolveFromSource(error, fallback);
    if (direct) {
      return direct;
    }
    const payloadCandidate = (error as Record<string, unknown> & { payload?: unknown }).payload;
    if (isRecord(payloadCandidate)) {
      const fromPayload = resolveFromSource(payloadCandidate, fallback);
      if (fromPayload) {
        return fromPayload;
      }
    }
  }

  if (error instanceof Error && typeof error.message === "string" && error.message) {
    return error.message;
  }

  return fallback;
};

