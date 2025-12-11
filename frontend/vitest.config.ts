// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    css: true,
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      exclude: [
        "node_modules/",
        "src/**/*.stories.{ts,tsx}",
        "src/**/*.d.ts",
        ".storybook/",
      ],
    },
  },
});
