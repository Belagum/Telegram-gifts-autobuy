// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import type { Preview } from "@storybook/react";
import "../src/app/styles/tokens.css";
import "../src/app/styles/global.css";

const preview: Preview = {
  parameters: {
    actions: { argTypesRegex: "^on[A-Z].*" },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
  },
};

export default preview;
