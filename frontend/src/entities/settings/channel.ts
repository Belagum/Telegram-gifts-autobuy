// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

export interface Channel {
  id: number;
  channelId: string;
  title: string | null;
  priceMin: number | null;
  priceMax: number | null;
  supplyMin: number | null;
  supplyMax: number | null;
}
