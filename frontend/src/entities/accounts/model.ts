// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

export interface Account {
  id: number;
  displayName: string;
  username: string | null;
  stars: number;
  isPremium: boolean;
  premiumUntil: string | null;
  lastCheckedAt: string | null;
}
