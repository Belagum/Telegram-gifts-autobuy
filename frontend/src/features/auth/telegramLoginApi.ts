// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import { httpClient } from "../../shared/api/httpClient";

export interface LoginPayload {
  api_profile_id?: number;
  phone?: string;
  login_id?: string;
  code?: string;
  password?: string;
}

export interface SendCodeResponse {
  login_id: string;
}

export interface ConfirmCodeResponse {
  ok?: boolean;
  need_2fa?: boolean;
  error?: string;
  error_code?: string;
  detail?: string;
  context?: Record<string, unknown>;
}

export interface ConfirmPasswordResponse {
  ok?: boolean;
  error?: string;
  error_code?: string;
  detail?: string;
  context?: Record<string, unknown>;
}

export const sendCode = async (payload: LoginPayload): Promise<SendCodeResponse> => {
  return httpClient<SendCodeResponse>("/auth/send_code", { method: "POST", body: payload });
};

export const confirmCode = async (payload: LoginPayload): Promise<ConfirmCodeResponse> => {
  return httpClient<ConfirmCodeResponse>("/auth/confirm_code", { method: "POST", body: payload });
};

export const confirmPassword = async (payload: LoginPayload): Promise<ConfirmPasswordResponse> => {
  return httpClient<ConfirmPasswordResponse>("/auth/confirm_password", { method: "POST", body: payload });
};

export const cancelLogin = async (payload: LoginPayload): Promise<{ ok?: boolean }> => {
  return httpClient<{ ok?: boolean }>("/auth/cancel", { method: "POST", body: payload });
};
