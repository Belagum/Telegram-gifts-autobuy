// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import type { Meta, StoryObj } from "@storybook/react";
import { Skeleton } from "./Skeleton";

const meta: Meta<typeof Skeleton> = {
  title: "Shared/Skeleton",
  component: Skeleton,
  args: {
    width: "100%",
    height: 24,
  },
};

export default meta;

type Story = StoryObj<typeof Skeleton>;

export const Default: Story = {};

export const Circle: Story = {
  args: {
    width: 48,
    height: 48,
    rounded: true,
  },
};
