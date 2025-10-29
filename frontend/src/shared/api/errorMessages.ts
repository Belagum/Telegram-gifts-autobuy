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

const getValidationMessage = (
  field: string, 
  type: string, 
  ctx?: Record<string, any>
): string => {
  // Специфичные сообщения для username
  if (field === "username") {
    if (type === "missing") return "Введите имя пользователя";
    if (type === "username_invalid_chars") return "Имя пользователя может содержать только латинские буквы и цифры";
    if (type === "string_too_short") return "Имя пользователя слишком короткое";
    if (type === "string_too_long") return "Имя пользователя слишком длинное";
  }
  
  // Специфичные сообщения для password
  if (field === "password") {
    if (type === "missing") return "Введите пароль";
    if (type === "password_too_short") {
      const minLength = ctx?.min_length || 12;
      return `Пароль должен содержать минимум ${minLength} символов`;
    }
    if (type === "password_no_uppercase") return "Пароль должен содержать хотя бы одну заглавную букву";
    if (type === "password_no_lowercase") return "Пароль должен содержать хотя бы одну строчную букву";
    if (type === "password_no_digit") return "Пароль должен содержать хотя бы одну цифру";
    if (type === "password_no_special") return "Пароль должен содержать хотя бы один специальный символ";
    if (type === "password_weak") return "Пароль слишком простой, выберите более сложный";
    if (type === "string_too_long") return "Пароль слишком длинный";
  }
  
  // Специфичные сообщения для email
  if (field === "email") {
    if (type === "missing") return "Введите email";
    if (type === "email_invalid_format") return "Некорректный формат email";
    if (type === "email") return "Некорректный формат email";
  }
  
  // Специфичные сообщения для phone
  if (field === "phone") {
    if (type === "missing") return "Введите номер телефона";
    if (type === "phone_invalid_format") return "Некорректный формат номера телефона";
  }
  
  // Специфичные сообщения для API credentials
  if (field === "api_id") {
    if (type === "missing") return "Введите API ID";
    if (type === "api_id_invalid") return "Некорректный API ID";
    if (type === "int_parsing") return "API ID должен быть числом";
  }
  
  if (field === "api_hash") {
    if (type === "missing") return "Введите API Hash";
    if (type === "api_hash_invalid") return "Некорректный API Hash";
  }
  
  if (field === "bot_token") {
    if (type === "missing") return "Введите Bot Token";
    if (type === "bot_token_invalid") return "Некорректный Bot Token";
  }
  
  // Специфичные сообщения для chat/target IDs
  if (field === "notify_chat_id" || field === "chat_id") {
    if (type === "missing") return "Введите Chat ID";
    if (type === "chat_id_invalid") return "Некорректный Chat ID";
    if (type === "int_parsing") return "Chat ID должен быть числом";
  }
  
  if (field === "buy_target_id" || field === "target_id") {
    if (type === "missing") return "Введите Target ID";
    if (type === "target_id_invalid") return "Некорректный Target ID";
    if (type === "int_parsing") return "Target ID должен быть числом";
  }
  
  // Общие сообщения для всех полей
  if (type === "missing") return "Поле обязательно для заполнения";
  if (type === "string_too_short") {
    const minLength = ctx?.min_length;
    return minLength ? `Минимум ${minLength} символов` : "Слишком короткое значение";
  }
  if (type === "string_too_long") {
    const maxLength = ctx?.max_length;
    return maxLength ? `Максимум ${maxLength} символов` : "Слишком длинное значение";
  }
  if (type === "value_error") return "Некорректное значение";
  if (type === "type_error") return "Неправильный тип данных";
  if (type === "string_type") return "Должно быть строкой";
  if (type === "int_parsing") return "Должно быть числом";
  if (type === "bool_parsing") return "Должно быть true или false";
  if (type === "email") return "Некорректный email";
  if (type === "url") return "Некорректный URL";
  if (type === "uuid") return "Некорректный UUID";
  if (type === "datetime_parsing") return "Некорректная дата";
  if (type === "json_invalid") return "Некорректный JSON";
  if (type === "regex") return "Некорректный формат";
  
  // Фоллбэк для неизвестных типов
  return `Ошибка в поле ${field}`;
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
  
  // Special handling for validation errors
  const errorValue = readStringProperty(source, "error");
  if (errorValue === "validation_error") {
    const context = readRecordProperty(source, "context");
    if (context) {
      const errors = context.errors;
      if (Array.isArray(errors) && errors.length > 0) {
        // Format validation errors: generate message from type and context
        const firstError = errors[0];
        if (firstError && typeof firstError === "object" && "field" in firstError && "type" in firstError) {
          const field = String(firstError.field);
          const type = String(firstError.type);
          const ctx = firstError.ctx as Record<string, any> | undefined;
          return getValidationMessage(field, type, ctx);
        }
      }
    }
    return "Ошибка валидации данных";
  }
  
  const errorCode = readStringProperty(source, "error_code");
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
    const payloadCandidate = (error as Record<string, unknown> & { payload?: unknown }).payload;
    if (isRecord(payloadCandidate)) {
      const fromPayload = resolveFromSource(payloadCandidate, fallback);
      if (fromPayload) {
        return fromPayload;
      }
    }
    
    const direct = resolveFromSource(error, fallback);
    if (direct) {
      return direct;
    }
  }

  if (error instanceof Error && typeof error.message === "string" && error.message) {
    return error.message;
  }

  return fallback;
};

