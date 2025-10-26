// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import { httpClient, streamNdjson } from "../../shared/api/httpClient";
import type { AccountDto, AccountRefreshEventDto } from "../../shared/api/dto";
import { mapAccount, mapAccountEvent } from "../../shared/api/adapters";
import type { Account } from "./model";

type AccountsEnvelope = {
  items?: unknown;
  accounts?: unknown;
  state?: unknown;
};

type AccountsResponse = AccountDto[] | AccountsEnvelope;

const isEnvelope = (value: AccountsResponse): value is AccountsEnvelope => {
  return typeof value === "object" && value !== null && !Array.isArray(value);
};

const isRefreshing = (value: AccountsEnvelope): boolean => {
  return value.state === "refreshing";
};

const extractAccountDtos = (value: AccountsResponse): AccountDto[] => {
  if (Array.isArray(value)) {
    return value;
  }
  if (Array.isArray(value.items)) {
    return value.items as AccountDto[];
  }
  if (Array.isArray(value.accounts)) {
    return value.accounts as AccountDto[];
  }
  return [];
};

export const listAccounts = async (): Promise<Account[]> => {
  const fetchOnce = () => httpClient<AccountsResponse>("/accounts?wait=1");

  let data: AccountsResponse = await fetchOnce();

  while (isEnvelope(data) && isRefreshing(data)) {
    data = await fetchOnce();
  }

  const items = extractAccountDtos(data);

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


