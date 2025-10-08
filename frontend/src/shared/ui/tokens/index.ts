// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

// В этом модуле храним типизированные дизайн-токены, чтобы переиспользовать их в коде.
export type SpacingToken =
  | "spacing-2xs"
  | "spacing-xs"
  | "spacing-sm"
  | "spacing-md"
  | "spacing-lg"
  | "spacing-xl";

export const spacing: Record<SpacingToken, string> = {
  "spacing-2xs": "var(--spacing-2xs)",
  "spacing-xs": "var(--spacing-xs)",
  "spacing-sm": "var(--spacing-sm)",
  "spacing-md": "var(--spacing-md)",
  "spacing-lg": "var(--spacing-lg)",
  "spacing-xl": "var(--spacing-xl)",
};

export type ColorToken =
  | "bg"
  | "bgElevated"
  | "surface"
  | "border"
  | "text"
  | "textMuted"
  | "accent"
  | "accentHover"
  | "danger"
  | "success"
  | "warning";

export const colors: Record<ColorToken, string> = {
  bg: "var(--color-bg)",
  bgElevated: "var(--color-bg-elevated)",
  surface: "var(--color-surface)",
  border: "var(--color-border)",
  text: "var(--color-text)",
  textMuted: "var(--color-text-muted)",
  accent: "var(--color-accent)",
  accentHover: "var(--color-accent-hover)",
  danger: "var(--color-danger)",
  success: "var(--color-success)",
  warning: "var(--color-warning)",
};

export const radius = {
  xs: "var(--radius-xs)",
  sm: "var(--radius-sm)",
  md: "var(--radius-md)",
  lg: "var(--radius-lg)",
} as const;

export const zIndex = {
  dropdown: "var(--z-dropdown)",
  modalBackdrop: "var(--z-modal-backdrop)",
  modal: "var(--z-modal)",
  toast: "var(--z-toast)",
} as const;

export const typography = {
  fontFamilyBase: "var(--font-family-base)",
  fontSizeBase: "var(--font-size-base)",
  lineHeightBase: "var(--line-height-base)",
} as const;
