// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

export interface Gift {
  id: string;
  title: string;
  price: number;
  supply: number | null;
  isLimited: boolean;
  animatedUrl: string | null;
  availableAmount?: number | null;
  totalAmount?: number | null;
  limitedPerUser?: boolean;
  perUserAvailable?: number | null;
  perUserRemains?: number | null;
  requiresPremium?: boolean;
  stickerFileId?: string | null;
  stickerUniqueId?: string | null;
  stickerMime?: string | null;
  locks?: Record<string, string | null> | null;
  lockedUntilDate?: string | null;
}

export interface GiftsStreamEvent {
  type: string;
  payload: Gift[];
}
