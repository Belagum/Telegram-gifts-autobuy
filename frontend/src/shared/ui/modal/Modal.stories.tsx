// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import type { Meta, StoryObj } from "@storybook/react";
import React from "react";
import { useArgs } from "@storybook/preview-api";
import { Modal } from "./Modal";
import type { ModalProps } from "./Modal";
import { Button } from "../button/Button";

const meta: Meta<typeof Modal> = {
  title: "Shared/Modal",
  component: Modal,
  args: {
    open: true,
    title: "Пример модального окна",
  },
};

export default meta;

type Story = StoryObj<typeof Modal>;

const ModalPreview: React.FC<ModalProps> = (args) => {
  const [{ open }, updateArgs] = useArgs();
  return (
    <>
      <Button onClick={() => updateArgs({ open: true })}>Открыть</Button>
      <Modal
        {...args}
        open={open}
        onClose={() => updateArgs({ open: false })}
        footer={<Button onClick={() => updateArgs({ open: false })}>Закрыть</Button>}
      >
        <p>Любой контент внутри модалки.</p>
      </Modal>
    </>
  );
};

export const Default: Story = {
  render: (args) => <ModalPreview {...args} />,
};
