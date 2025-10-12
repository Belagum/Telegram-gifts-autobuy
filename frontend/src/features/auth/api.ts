// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import { httpClient } from "../../shared/api/httpClient";
import type { SessionDto } from "../../shared/api/dto";
import { mapSession } from "../../shared/api/adapters";
import type { SessionUser } from "../../entities/users/model";

export interface Credentials {
  username: string;
  password: string;
}

export interface LoginCredentials extends Credentials {
  rememberMe?: boolean;
}

export const register = async (credentials: Credentials): Promise<SessionUser> => {
  const dto = await httpClient<SessionDto>("/auth/register", {
    method: "POST",
    body: credentials,
  });
  return mapSession(dto);
};

export const login = async (credentials: LoginCredentials): Promise<SessionUser> => {
  const dto = await httpClient<SessionDto>("/auth/login", {
    method: "POST",
    body: {
      username: credentials.username,
      password: credentials.password,
      remember_me: credentials.rememberMe || false,
    },
  });
  return mapSession(dto);
};

export const logout = async (): Promise<void> => {
  await httpClient("/auth/logout", { method: "DELETE", parseJson: false });
};

export const me = async (): Promise<SessionUser> => {
  const dto = await httpClient<SessionDto>("/me");
  return mapSession(dto);
};
