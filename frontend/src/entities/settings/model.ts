// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

export interface Settings {
  botToken: string | null;
  notifyChatId: string | null;
  buyTargetId: string | null;
  buyTargetOnFailOnly: boolean;
}

export interface GiftsSettings {
  autoRefresh: boolean;
}
