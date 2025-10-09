// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";

/**
 * automatically resizes a popup window (opened via window.open) to fit its content.
 */
export const usePopupAutoSize = (enabled: boolean = true): void => {
  React.useEffect(() => {
    if (!enabled) return;

    const inPopup = typeof window !== "undefined" && !!(window as Window).opener;
    if (!inPopup) return;

    let rafId: number | null = null;
    let tId: number | null = null;
    let lastWidth = 0;
    let lastHeight = 0;

    const resizeToContent = () => {
      // the maximum content size
      const docEl = document.documentElement;
      const body = document.body;
      const contentWidth = Math.max(
        body.scrollWidth,
        docEl.scrollWidth,
        body.offsetWidth,
        docEl.offsetWidth,
        docEl.clientWidth
      );
      const contentHeight = Math.max(
        body.scrollHeight,
        docEl.scrollHeight,
        body.offsetHeight,
        docEl.offsetHeight,
        docEl.clientHeight
      );

      const extraW = (window.outerWidth || 0) - (window.innerWidth || 0);
      const extraH = (window.outerHeight || 0) - (window.innerHeight || 0);

      const buffer = 8;

      let targetOuterW = Math.ceil(contentWidth + extraW + buffer);
      let targetOuterH = Math.ceil(contentHeight + extraH + buffer);

      // available screen space
      const maxW = window.screen.availWidth || window.screen.width || targetOuterW;
      const maxH = window.screen.availHeight || window.screen.height || targetOuterH;
      targetOuterW = Math.min(targetOuterW, maxW);
      targetOuterH = Math.min(targetOuterH, maxH);

      // avoid redundant resize calls
      if (Math.abs(targetOuterW - lastWidth) < 2 && Math.abs(targetOuterH - lastHeight) < 2) return;

      try {
        window.resizeTo(targetOuterW, targetOuterH);
        lastWidth = targetOuterW;
        lastHeight = targetOuterH;
      } catch {
        // ignore if browser blocks programmatic resize
      }
    };

    const schedule = () => {
      if (rafId != null) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(resizeToContent);
    };

    // Initial
    schedule();
    tId = window.setTimeout(schedule, 150);

    window.addEventListener("load", schedule);
    const mo = new MutationObserver(schedule);
    mo.observe(document.body, { childList: true, subtree: true, attributes: true, characterData: true });

    // listen to size changes of root node
    const ro = ("ResizeObserver" in window)
      ? new ResizeObserver(schedule)
      : null;
    if (ro) ro.observe(document.documentElement);

    return () => {
      if (rafId != null) cancelAnimationFrame(rafId);
      if (tId != null) clearTimeout(tId);
      window.removeEventListener("load", schedule);
      mo.disconnect();
      if (ro) ro.disconnect();
    };
  }, [enabled]);
};

