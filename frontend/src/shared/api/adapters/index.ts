// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import type {
  AccountDto,
  AccountRefreshEventDto,
  ApiProfileDto,
  ChannelDto,
  GiftDto,
  GiftsSettingsDto,
  GiftsStreamEventDto,
  SessionDto,
  SettingsDto,
} from "../dto";
import type { SessionUser } from "../../../entities/users/model";
import type { Account } from "../../../entities/accounts/model";
import type { ApiProfile } from "../../../entities/accounts/apiProfile";
import type { Channel } from "../../../entities/settings/channel";
import type { Gift, GiftsStreamEvent } from "../../../entities/gifts/model";
import type { GiftsSettings, Settings } from "../../../entities/settings/model";

export const mapSession = (dto: SessionDto): SessionUser => ({
  id: dto.id,
  username: dto.username,
});

export const mapAccount = (dto: AccountDto): Account => ({
  id: dto.id,
  displayName: dto.first_name ?? "Без имени",
  username: dto.username,
  stars: dto.stars,
  isPremium: dto.is_premium,
  premiumUntil: dto.premium_until,
  lastCheckedAt: dto.last_checked_at,
});

export const mapAccountEvent = (dto: AccountRefreshEventDto) => ({
  ...dto,
  account: dto.account ? mapAccount(dto.account) : undefined,
});

export const mapApiProfile = (dto: ApiProfileDto): ApiProfile => ({
  id: dto.id,
  name: dto.name,
  apiId: dto.api_id,
});

export const mapChannel = (dto: ChannelDto): Channel => ({
  id: dto.id,
  channelId: dto.channel_id,
  title: (dto.title ?? null) && dto.title.trim() !== "" ? dto.title : null,
  priceMin: dto.price_min,
  priceMax: dto.price_max,
  supplyMin: dto.supply_min,
  supplyMax: dto.supply_max,
});

export const mapGift = (dto: GiftDto): Gift => ({
  id: dto.id,
  title: dto.title,
  price: dto.price,
  supply: dto.supply,
  isLimited: dto.is_limited,
  animatedUrl: dto.animated_url,
  availableAmount: dto.available_amount ?? null,
  requiresPremium: dto.require_premium ?? false,
  stickerFileId: dto.sticker_file_id ?? null,
  stickerUniqueId: dto.sticker_unique_id ?? null,
  stickerMime: dto.sticker_mime ?? null,
});

export const mapGiftsStreamEvent = (dto: GiftsStreamEventDto): GiftsStreamEvent => ({
  type: dto.type,
  payload: dto.payload.map(mapGift),
});

export const mapSettings = (dto: SettingsDto): Settings => ({
  botToken: dto.bot_token,
  notifyChatId: dto.notify_chat_id,
  buyTargetId: dto.buy_target_id,
  buyTargetOnFailOnly: Boolean(dto.buy_target_on_fail_only),
});

export const mapGiftsSettings = (dto: GiftsSettingsDto): GiftsSettings => ({
  autoRefresh: dto.auto_refresh,
});
