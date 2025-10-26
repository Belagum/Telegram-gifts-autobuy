// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

export interface ApiErrorDto {
  error?: string;
  detail?: string;
  error_code?: string;
  context?: Record<string, unknown>;
}

export interface SessionDto {
  id: number;
  username: string;
}

export interface AccountDto {
  id: number;
  first_name: string | null;
  username: string | null;
  stars: number;
  is_premium: boolean;
  premium_until: string | null;
  last_checked_at: string | null;
}

export interface AccountRefreshEventDto {
  stage?: string;
  error?: string;
  error_code?: string;
  context?: Record<string, unknown>;
  done?: boolean;
  account?: AccountDto;
}

export interface ApiProfileDto {
  id: number;
  name: string;
  api_id: number;
}

export interface ChannelDto {
  id: number;
  channel_id: string;
  title: string | null;
  price_min: number | null;
  price_max: number | null;
  supply_min: number | null;
  supply_max: number | null;
}

export interface GiftDto {
  id: string;
  title: string;
  price: number;
  supply: number | null;
  is_limited: boolean;
  available_amount?: number | null;
  total_amount?: number | null;
  limited_per_user?: boolean | null;
  per_user_available?: number | null;
  per_user_remains?: number | null;
  require_premium?: boolean;
  sticker_file_id?: string | null;
  sticker_unique_id?: string | null;
  sticker_mime?: string | null;
  animated_url: string | null;
  locks?: Record<string, string | null> | null;
  locked_until_date?: string | null;
}

export interface GiftsSettingsDto {
  auto_refresh: boolean;
}

export interface SettingsDto {
  bot_token: string | null;
  notify_chat_id: string | null;
  buy_target_id: string | null;
  buy_target_on_fail_only: boolean | null;
}

export interface GiftsStreamEventDto {
  type: string;
  payload: GiftDto[];
}
