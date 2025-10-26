// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

const DEFAULT_ERROR_MESSAGE = "Что-то пошло не так, попробуйте ещё раз";

interface ResolverArgs {
  errorCode?: string;
  context?: Record<string, unknown>;
}

type ErrorResolver = (args: ResolverArgs) => string;
type SuccessResolver = (context?: Record<string, unknown>) => string;

const formatRemainingSeconds = (value: unknown): string | null => {
  const seconds = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(seconds)) {
    return null;
  }
  let remaining = Math.max(0, Math.floor(seconds));
  const days = Math.floor(remaining / 86400);
  remaining %= 86400;
  const hours = Math.floor(remaining / 3600);
  remaining %= 3600;
  const minutes = Math.floor(remaining / 60);
  remaining %= 60;
  const parts: string[] = [];
  if (days) parts.push(`${days}д`);
  if (hours) parts.push(`${hours}ч`);
  if (minutes) parts.push(`${minutes}м`);
  if (!parts.length || remaining) parts.push(`${remaining}с`);
  return parts.join(" ");
};

const formatNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
};

const formatFields = (fields: unknown): string | null => {
  if (Array.isArray(fields) && fields.length) {
    return fields.map(String).join(" / ");
  }
  return null;
};

const TELEGRAM_RPC_MESSAGES: Record<string, string> = {
  PHONE_CODE_INVALID: "Неверный код подтверждения из Telegram.",
  PHONE_CODE_EXPIRED: "Срок действия кода истёк. Запросите новый код.",
  SESSION_PASSWORD_NEEDED: "Требуется пароль двухфакторной авторизации.",
  FLOOD_WAIT: "Телеграм временно ограничил отправку запросов. Попробуйте позже.",
};

const ERROR_MESSAGE_RESOLVERS: Record<string, ErrorResolver> = {
  internal_error: () => "Произошла внутренняя ошибка. Попробуйте позже.",
  csrf: () => "Не удалось подтвердить запрос. Обновите страницу и повторите попытку.",
  api_id_and_api_hash_required: () => "Укажите API ID и API HASH.",
  duplicate_api_id: ({ context }) => {
    const existing = formatNumber(context?.existing_id);
    return existing
      ? `API ID уже используется (профиль №${existing}).`
      : "API ID уже используется.";
  },
  duplicate_api_hash: ({ context }) => {
    const existing = formatNumber(context?.existing_id);
    return existing
      ? `API HASH уже используется (профиль №${existing}).`
      : "API HASH уже используется.";
  },
  api_profile_in_use: ({ context }) => {
    const accounts = formatNumber(context?.accounts);
    return accounts && accounts > 0
      ? `API профиль используется ${accounts} аккаунтами. Удалите или переназначьте их.`
      : "API профиль используется другими аккаунтами.";
  },
  phone_and_api_profile_id_required: () => "Укажите номер телефона и API профиль.",
  phone_already_added: ({ context }) => {
    const accountId = formatNumber(context?.account_id);
    const phone = typeof context?.phone === "string" ? context.phone : null;
    if (accountId && phone) {
      return `Номер ${phone} уже добавлен (аккаунт №${accountId}).`;
    }
    return "Этот номер уже привязан к другому аккаунту.";
  },
  login_id_and_code_required: () => "Введите код из Telegram.",
  login_id_and_password_required: () => "Введите пароль двухфакторной авторизации.",
  log_id_required: () => "Не указан идентификатор сессии входа.",
  login_id_not_found: () => "Сессия входа не найдена или истекла. Начните заново.",
  validation_error: ({ context }) => {
    const fields = formatFields(context?.fields);
    if (fields) {
      return `Некорректные данные в полях: ${fields}.`;
    }
    return "Некорректные данные. Проверьте форму и повторите попытку.";
  },
  telegram_rpc: ({ errorCode }) => {
    if (errorCode && TELEGRAM_RPC_MESSAGES[errorCode]) {
      return TELEGRAM_RPC_MESSAGES[errorCode];
    }
    return errorCode ? `Ошибка Telegram (${errorCode}).` : "Ошибка Telegram. Попробуйте позже.";
  },
  unexpected: ({ errorCode }) => {
    switch (errorCode) {
      case "start_login_failed":
        return "Не удалось отправить код. Попробуйте ещё раз.";
      case "complete_login_failed":
        return "Не удалось подтвердить код. Попробуйте ещё раз.";
      case "confirm_password_failed":
        return "Не удалось подтвердить пароль. Попробуйте ещё раз.";
      default:
        return "Произошла неожиданная ошибка. Попробуйте позже.";
    }
  },
  session_invalid: () => "Сессия аккаунта недействительна. Авторизуйтесь заново.",
  account_refresh_failed: () => "Не удалось обновить аккаунт. Попробуйте ещё раз позднее.",
  bad_channel_id: () => "Некорректный ID канала.",
  bad_range: ({ context }) => {
    const fields = formatFields(context?.fields);
    return fields
      ? `Некорректный диапазон для полей ${fields}.`
      : "Некорректный диапазон значений.";
  },
  channel_not_joined: () => "Ни один аккаунт не состоит в указанном канале.",
  duplicate_channel: () => "Канал уже добавлен в список.",
  no_accounts: () => "Нет доступных аккаунтов для операции.",
  api_profile_missing: () => "Для аккаунта не выбран API профиль.",
  account_id_invalid: () => "Некорректный ID аккаунта.",
  account_not_found: () => "Аккаунт не найден.",
  gift_id_invalid: () => "Некорректный ID подарка.",
  gift_not_found: () => "Подарок не найден.",
  gift_unavailable: () => "Подарок недоступен для покупки.",
  requires_premium: () => "Для отправки подарка нужен Telegram Premium.",
  peer_id_invalid: () => "Telegram не нашёл получателя. Проверьте ID или начните диалог вручную.",
  target_id_required: () => "Укажите получателя подарка.",
  target_id_invalid: () => "Некорректный ID получателя.",
  bad_tgs: () => "Некорректный файл стикера.",
  no_bot_token: () => "Укажите Bot token в настройках.",
  download_failed: () => "Не удалось загрузить файл. Попробуйте ещё раз.",
  settings_update_failed: () => "Не удалось сохранить настройки. Попробуйте ещё раз.",
  insufficient_balance: ({ context }) => {
    const balance = formatNumber(context?.balance);
    const required = formatNumber(context?.required);
    if (balance !== null && required !== null) {
      return `Недостаточно звёзд: доступно ${balance}⭐, требуется ${required}⭐.`;
    }
    return "Недостаточно звёзд для покупки подарка.";
  },
  gift_locked: ({ context }) => {
    const accountId = formatNumber(context?.account_id);
    const until = typeof context?.locked_until === "string" ? context.locked_until : null;
    const remaining = formatRemainingSeconds(context?.remaining_seconds);
    const parts: string[] = [];
    if (accountId) {
      parts.push(`Аккаунт №${accountId}`);
    } else {
      parts.push("Аккаунт");
    }
    if (until) {
      parts.push(`заблокирован до ${until}`);
    } else {
      parts.push("заблокирован на отправку подарка");
    }
    if (remaining) {
      parts.push(`(ещё ${remaining})`);
    }
    return parts.join(" ");
  },
  start_login_failed: () => "Не удалось отправить код. Попробуйте ещё раз.",
  complete_login_failed: () => "Не удалось подтвердить код. Попробуйте ещё раз.",
  confirm_password_failed: () => "Не удалось подтвердить пароль. Попробуйте ещё раз.",
  gift_send_failed: () => "Не удалось отправить подарок. Попробуйте позже.",
  channels_list_failed: () => "Не удалось загрузить список каналов. Попробуйте ещё раз.",
  channel_create_failed: () => "Не удалось добавить канал. Попробуйте ещё раз.",
  channel_update_failed: () => "Не удалось обновить канал. Попробуйте ещё раз.",
  channel_delete_failed: () => "Не удалось удалить канал. Попробуйте ещё раз.",
};

const ERROR_CODE_MESSAGE_RESOLVERS: Record<string, ErrorResolver> = {
  AUTH_KEY_UNREGISTERED: () => "Сессия аккаунта недействительна. Авторизуйтесь заново.",
  start_login_failed: ERROR_MESSAGE_RESOLVERS.start_login_failed,
  complete_login_failed: ERROR_MESSAGE_RESOLVERS.complete_login_failed,
  confirm_password_failed: ERROR_MESSAGE_RESOLVERS.confirm_password_failed,
};

const SUCCESS_MESSAGE_RESOLVERS: Record<string, SuccessResolver> = {
  gift_sent: (context) => {
    const giftId = context?.gift_id ?? context?.giftId;
    const accountId = context?.account_id ?? context?.accountId;
    const targetId = context?.target_id ?? context?.targetId;
    const parts: string[] = ["Подарок отправлен успешно."];
    if (giftId !== undefined) {
      parts.push(`ID подарка: ${giftId}.`);
    }
    if (accountId !== undefined) {
      parts.push(`Аккаунт: ${accountId}.`);
    }
    if (targetId !== undefined) {
      parts.push(`Получатель: ${targetId}.`);
    }
    return parts.join(" ");
  },
};

const ACCOUNT_STAGE_MESSAGES: Record<string, string> = {
  connect: "Соединение с Telegram…",
  profile: "Проверяем профиль…",
  stars: "Проверяем баланс звёзд…",
  premium: "Проверяем статус Premium…",
  save: "Сохраняем данные…",
  done: "Готово",
};

export const resolveErrorMessage = (
  error?: string,
  errorCode?: string,
  context?: Record<string, unknown>,
  fallback: string = DEFAULT_ERROR_MESSAGE,
): string => {
  if (error) {
    const resolver = ERROR_MESSAGE_RESOLVERS[error];
    if (resolver) {
      return resolver({ errorCode, context });
    }
  }
  if (errorCode) {
    const resolver = ERROR_CODE_MESSAGE_RESOLVERS[errorCode];
    if (resolver) {
      return resolver({ errorCode, context });
    }
  }
  if (error) {
    return error;
  }
  if (errorCode) {
    return errorCode;
  }
  return fallback;
};

export const resolveSuccessMessage = (
  result?: string,
  context?: Record<string, unknown>,
  fallback = "Операция успешно выполнена",
): string => {
  if (result) {
    const resolver = SUCCESS_MESSAGE_RESOLVERS[result];
    if (resolver) {
      return resolver(context ?? undefined);
    }
  }
  return fallback;
};

export const resolveAccountStageMessage = (stage?: string | null): string => {
  if (!stage) {
    return "Обновление аккаунта…";
  }
  return ACCOUNT_STAGE_MESSAGES[stage] ?? `Этап: ${stage}`;
};
