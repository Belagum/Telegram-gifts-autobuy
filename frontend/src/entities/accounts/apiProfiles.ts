// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import { httpClient } from "../../shared/api/httpClient";
import type { ApiProfileDto } from "../../shared/api/dto";
import { mapApiProfile } from "../../shared/api/adapters";
import type { ApiProfile } from "./apiProfile";

export const listApiProfiles = async (): Promise<ApiProfile[]> => {
  const dto = await httpClient<ApiProfileDto[] | { items?: ApiProfileDto[] }>("/apiprofiles");
  const items = Array.isArray(dto) ? dto : Array.isArray(dto.items) ? dto.items : [];
  return items.map(mapApiProfile);
};

export const createApiProfile = async (payload: {
  api_id: number;
  api_hash: string;
  name: string;
}): Promise<ApiProfile> => {
  const dto = await httpClient<ApiProfileDto>("/apiprofile", {
    method: "POST",
    body: payload,
  });
  return mapApiProfile(dto);
};

export const renameApiProfile = async (id: number, name: string): Promise<ApiProfile> => {
  const dto = await httpClient<ApiProfileDto>(`/apiprofile/${id}`, {
    method: "PATCH",
    body: { name },
  });
  return mapApiProfile(dto);
};

export const deleteApiProfile = async (id: number): Promise<void> => {
  await httpClient(`/apiprofile/${id}`, { method: "DELETE", parseJson: false });
};
