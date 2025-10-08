// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import { httpClient } from "../../shared/api/httpClient";
import { createSseStream } from "../../shared/api/eventSource";
import type { GiftDto, GiftsSettingsDto, GiftsStreamEventDto } from "../../shared/api/dto";
import { mapGift, mapGiftsStreamEvent, mapGiftsSettings } from "../../shared/api/adapters";
import type { Gift, GiftsStreamEvent } from "./model";
import type { GiftsSettings } from "../settings/model";

export const listGifts = async (): Promise<Gift[]> => {
  const dto = await httpClient<GiftDto[]>("/gifts");
  return dto.map(mapGift);
};

export const refreshGifts = async (): Promise<{ items: Gift[] }> => {
  const dto = await httpClient<{ items?: GiftDto[]; gifts?: GiftDto[] }>("/gifts/refresh", { method: "POST" });
  const items = Array.isArray(dto.items)
    ? dto.items
    : Array.isArray(dto.gifts)
    ? dto.gifts
    : [];
  return { items: items.map(mapGift) };
};

export const getGiftsSettings = async (): Promise<GiftsSettings> => {
  const dto = await httpClient<GiftsSettingsDto>("/gifts/settings");
  return mapGiftsSettings(dto);
};

export const setGiftsSettings = async (autoRefresh: boolean): Promise<GiftsSettings> => {
  const dto = await httpClient<GiftsSettingsDto>("/gifts/settings", {
    method: "POST",
    body: { auto_refresh: autoRefresh },
  });
  return mapGiftsSettings(dto);
};

export const subscribeGiftsStream = (
  onEvent: (event: GiftsStreamEvent) => void,
  onError?: (error: Event) => void,
) => {
  return createSseStream<GiftsStreamEventDto>({
    path: "/api/gifts/stream",
    event: "gifts",
    onEvent: (dto) => onEvent(mapGiftsStreamEvent(dto)),
    onError,
  });
};
