// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import type { StorybookConfig } from "@storybook/react-vite";

const config: StorybookConfig = {
  framework: {
    name: "@storybook/react-vite",
    options: {},
  },
  stories: ["../src/**/*.stories.@(ts|tsx)"],
  addons: ["@storybook/addon-essentials", "@storybook/addon-interactions", "@storybook/addon-a11y"],
  docs: {
    autodocs: "tag",
  },
  viteFinal: async (config) => {
    config.server = config.server ?? {};
    config.server.headers = {
      ...(config.server.headers ?? {}),
      "Content-Security-Policy":
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; font-src 'self'; frame-ancestors 'none'",
    };
    return config;
  },
};

export default config;
