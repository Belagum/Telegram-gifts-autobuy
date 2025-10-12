// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import { httpClient } from "../../shared/api/httpClient";
import type { SettingsDto, ChannelDto } from "../../shared/api/dto";
import { mapChannel, mapSettings } from "../../shared/api/adapters";
import type { Settings } from "./model";
import type { Channel } from "./channel";

export const getSettings = async (): Promise<Settings> => {
  const dto = await httpClient<SettingsDto>("/settings");
  return mapSettings(dto);
};

export const setSettings = async (settings: Settings): Promise<Settings> => {
  const dto = await httpClient<SettingsDto>("/settings", {
    method: "POST",
    body: {
      bot_token: settings.botToken,
      notify_chat_id: settings.notifyChatId,
      buy_target_id: settings.buyTargetId,
      buy_target_on_fail_only: settings.buyTargetOnFailOnly,
    },
  });
  return mapSettings(dto);
};

type ChannelsResponse = ChannelDto[] | { items?: ChannelDto[]; channels?: ChannelDto[] } | null | string;

const extractChannelDtos = (payload: ChannelsResponse): ChannelDto[] => {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (payload && typeof payload === "object") {
    const withCollections = payload as { items?: ChannelDto[]; channels?: ChannelDto[] };
    if (Array.isArray(withCollections.items)) {
      return withCollections.items;
    }
    if (Array.isArray(withCollections.channels)) {
      return withCollections.channels;
    }
  }
  return [];
};

export const listChannels = async (): Promise<Channel[]> => {
  const data = await httpClient<ChannelsResponse>("/channels");
  return extractChannelDtos(data).map(mapChannel);
};

export const createChannel = async (payload: Partial<Channel>): Promise<void> => {
  await httpClient("/channel", {
    method: "POST",
    body: {
      channel_id: payload.channelId,
      title: payload.title ?? null,
      price_min: payload.priceMin ?? null,
      price_max: payload.priceMax ?? null,
      supply_min: payload.supplyMin ?? null,
      supply_max: payload.supplyMax ?? null,
    },
    parseJson: false,
  });
};

export const updateChannel = async (id: number, payload: Partial<Channel>): Promise<void> => {
  const body: Record<string, unknown> = {};
  if ("title" in payload) body.title = payload.title ?? null;
  if ("priceMin" in payload) body.price_min = payload.priceMin ?? null;
  if ("priceMax" in payload) body.price_max = payload.priceMax ?? null;
  if ("supplyMin" in payload) body.supply_min = payload.supplyMin ?? null;
  if ("supplyMax" in payload) body.supply_max = payload.supplyMax ?? null;

  await httpClient(`/channel/${id}`, {
    method: "PATCH",
    body,
    parseJson: false,
  });
};

export const deleteChannel = async (id: number): Promise<void> => {
  await httpClient(`/channel/${id}`, { method: "DELETE", parseJson: false });
};
