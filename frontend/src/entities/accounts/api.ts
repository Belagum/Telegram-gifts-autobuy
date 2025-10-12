// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import { httpClient, streamNdjson } from "../../shared/api/httpClient";
import type { AccountDto, AccountRefreshEventDto } from "../../shared/api/dto";
import { mapAccount, mapAccountEvent } from "../../shared/api/adapters";
import type { Account } from "./model";

export const listAccounts = async (): Promise<Account[]> => {
  type AccountsResp = AccountDto[] | { items?: AccountDto[]; accounts?: AccountDto[]; state?: string };

  const fetchOnce = () => httpClient<AccountsResp>("/accounts?wait=1");

  let data = await fetchOnce();

  while (typeof data === "object" && data !== null && !Array.isArray(data) && (data as any).state === "refreshing") {
    data = await fetchOnce();
  }

  const items = Array.isArray(data)
    ? data
    : Array.isArray((data as any)?.items)
    ? (data as any).items
    : Array.isArray((data as any)?.accounts)
    ? (data as any).accounts
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


