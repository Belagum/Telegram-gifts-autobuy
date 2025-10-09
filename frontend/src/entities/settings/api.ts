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

export const listChannels = async (): Promise<Channel[]> => {
  const dto = await httpClient<ChannelDto[] | null | string>("/channels");
  if (!Array.isArray(dto)) return [];
  return dto.map(mapChannel);
};

export const createChannel = async (payload: Partial<Channel>): Promise<Channel> => {
  const dto = await httpClient<ChannelDto>("/channel", {
    method: "POST",
    body: {
      channel_id: payload.channelId,
      title: payload.title ?? null,
      price_min: payload.priceMin ?? null,
      price_max: payload.priceMax ?? null,
      supply_min: payload.supplyMin ?? null,
      supply_max: payload.supplyMax ?? null,
    },
  });
  return mapChannel(dto);
};

export const updateChannel = async (id: number, payload: Partial<Channel>): Promise<Channel> => {
  const dto = await httpClient<ChannelDto>(`/channel/${id}`, {
    method: "PATCH",
    body: {
      channel_id: payload.channelId,
      title: payload.title ?? null,
      price_min: payload.priceMin ?? null,
      price_max: payload.priceMax ?? null,
      supply_min: payload.supplyMin ?? null,
      supply_max: payload.supplyMax ?? null,
    },
  });
  return mapChannel(dto);
};

export const deleteChannel = async (id: number): Promise<void> => {
  await httpClient(`/channel/${id}`, { method: "DELETE", parseJson: false });
};
