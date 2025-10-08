// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import type { Meta, StoryObj } from "@storybook/react";
import { Select } from "./Select";

const meta: Meta<typeof Select> = {
  title: "Shared/Select",
  component: Select,
  args: {
    options: [
      { label: "Первый", value: "1" },
      { label: "Второй", value: "2" },
    ],
  },
};

export default meta;

type Story = StoryObj<typeof Select>;

export const Default: Story = {};

export const WithError: Story = {
  args: {
    error: "Выберите значение",
  },
};
