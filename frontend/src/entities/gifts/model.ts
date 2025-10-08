// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

export interface Gift {
  id: number;
  title: string;
  price: number;
  supply: number | null;
  isLimited: boolean;
  animatedUrl: string | null;
  availableAmount?: number | null;
  requiresPremium?: boolean;
  stickerFileId?: string | null;
  stickerUniqueId?: string | null;
  stickerMime?: string | null;
}

export interface GiftsStreamEvent {
  type: string;
  payload: Gift[];
}
