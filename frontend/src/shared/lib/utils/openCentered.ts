// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

/**
 * Validates URL to prevent javascript: and other dangerous protocols.
 * Only allows http:, https:, and relative URLs starting with '/'.
 */
const isValidUrl = (url: string): boolean => {
  // Allow relative URLs starting with '/'
  if (url.startsWith("/")) {
    return true;
  }

  try {
    const parsed = new URL(url, window.location.origin);
    // Only allow http and https protocols
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    // Invalid URL format
    return false;
  }
};

export const openCentered = (url: string, name = "_blank", width = 520, height = 700) => {
  // Security: validate URL to prevent javascript: injection
  if (!isValidUrl(url)) {
    console.warn("openCentered: blocked potentially unsafe URL");
    return;
  }

  const bx = window.screenX ?? window.screenLeft ?? 0;
  const by = window.screenY ?? window.screenTop ?? 0;
  const bw = window.outerWidth ?? window.innerWidth;
  const bh = window.outerHeight ?? window.innerHeight;

  const left = Math.round(bx + (bw - width) / 2);
  const top = Math.round(by + (bh - height) / 2);

  const windowName =
    name === "_blank" ? `win_${Date.now()}_${Math.random().toString(36).slice(2)}` : name;

  const features = [
    "noopener",
    "noreferrer",
    "toolbar=no",
    "location=no",
    "status=no",
    "menubar=no",
    "scrollbars=yes",
    "resizable=yes",
    `width=${width}`,
    `height=${height}`,
    `left=${left}`,
    `top=${top}`,
    `screenX=${left}`,
    `screenY=${top}`,
  ].join(",");

  const win = window.open(url, windowName, features);
  if (win) {
    win.focus();
  }
};
