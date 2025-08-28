// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova orig

export default function openCentered(url, name="_blank", w=520, h=700){
  const bx = window.screenX ?? window.screenLeft ?? 0;
  const by = window.screenY ?? window.screenTop  ?? 0;
  const bw = window.outerWidth  ?? window.innerWidth;
  const bh = window.outerHeight ?? window.innerHeight;

  const left = Math.round(bx + (bw - w) / 2);
  const top  = Math.round(by + (bh - h) / 2);

  const winName = name === "_blank"
    ? `win_${Date.now()}_${Math.random().toString(36).slice(2)}`
    : name;

  const feat = [
    "noopener","noreferrer",
    "toolbar=no","location=no","status=no","menubar=no",
    "scrollbars=yes","resizable=yes",
    `width=${w}`,`height=${h}`,
    `left=${left}`,`top=${top}`,         // Chrome/Edge
    `screenX=${left}`,`screenY=${top}`   // Firefox
  ].join(",");

  const win = window.open(url, winName, feat);
  if (win) win.focus();
}
