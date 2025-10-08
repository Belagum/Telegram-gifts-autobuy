// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import { httpClient, streamNdjson } from "../../shared/api/httpClient";
import type { AccountDto, AccountRefreshEventDto } from "../../shared/api/dto";
import { mapAccount, mapAccountEvent } from "../../shared/api/adapters";
import type { Account } from "./model";

export const listAccounts = async (): Promise<Account[]> => {
  const data = await httpClient<AccountDto[] | { items?: AccountDto[]; accounts?: AccountDto[] }>("/accounts");
  const items = Array.isArray(data)
    ? data
    : Array.isArray(data.items)
    ? data.items
    : Array.isArray(data.accounts)
    ? data.accounts
    : [];
  return items.map(mapAccount);
};

export const refreshAccount = async (id: number): Promise<Account> => {
  const data = await httpClient<AccountDto>(`/account/${id}/refresh`, { method: "POST" });
  return mapAccount(data);
};

export const refreshAccountStream = async (
  id: number,
  onEvent: (event: ReturnType<typeof mapAccountEvent>) => void,
) => {
  await streamNdjson<AccountRefreshEventDto>({
    path: `/account/${id}/refresh`,
    method: "POST",
    onEvent: (event) => onEvent(mapAccountEvent(event)),
  });
};
