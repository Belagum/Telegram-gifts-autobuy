// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import type { Meta, StoryObj } from "@storybook/react";
import { Input } from "./Input";

const meta: Meta<typeof Input> = {
  title: "Shared/Input",
  component: Input,
  args: {
    placeholder: "Введите значение",
  },
};

export default meta;

type Story = StoryObj<typeof Input>;

export const Default: Story = {};

export const WithError: Story = {
  args: {
    error: "Ошибка валидации",
  },
};
