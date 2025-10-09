// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

/* eslint-disable import/no-unresolved */
import RefreshRuntime from '/@react-refresh';

declare global {
  interface Window {
    __vite_plugin_react_preamble_installed__?: boolean;
    $RefreshReg$?: (type: unknown, id?: string) => void;
    $RefreshSig$?: () => (type: unknown) => unknown;
  }
}

if (!window.__vite_plugin_react_preamble_installed__) {
  RefreshRuntime.injectIntoGlobalHook(window);
  window.$RefreshReg$ = () => {};
  window.$RefreshSig$ = () => (type) => type;
  window.__vite_plugin_react_preamble_installed__ = true;
}

export {};
