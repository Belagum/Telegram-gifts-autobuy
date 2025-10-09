// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import { Modal } from "../../shared/ui/modal/Modal";
import { Button } from "../../shared/ui/button/Button";
import { ConfirmDialog } from "../../shared/ui/modal/ConfirmDialog";
import { listChannels, deleteChannel } from "../../entities/settings/api";
import type { Channel } from "../../entities/settings/channel";
import { showError, showSuccess } from "../../shared/ui/feedback/toast";
import { EditChannelModal } from "./EditChannelModal";
import "./channels-modal.css";

export interface ChannelsModalProps {
  open: boolean;
  onClose: () => void;
}

export const ChannelsModal: React.FC<ChannelsModalProps> = ({ open, onClose }) => {
  const [channels, setChannels] = React.useState<Channel[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [confirm, setConfirm] = React.useState<Channel | null>(null);
  const [editor, setEditor] = React.useState<Channel | null | undefined>(undefined);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const items = await listChannels();
      setChannels(items);
    } catch (error) {
      showError(error, "Не удалось загрузить каналы");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    if (open) {
      void load();
    }
  }, [open, load]);

  const handleDelete = async () => {
    if (!confirm) return;
    try {
      await deleteChannel(confirm.id);
      setChannels((current) => current.filter((channel) => channel.id !== confirm.id));
      showSuccess("Канал удалён");
    } catch (error) {
      showError(error, "Не удалось удалить канал");
    } finally {
      setConfirm(null);
    }
  };

  const describeChannel = (channel: Channel) => {
    const priceRange = [channel.priceMin, channel.priceMax].filter((value) => value != null).join(" – ");
    const supplyRange = [channel.supplyMin, channel.supplyMax].filter((value) => value != null).join(" – ");
    return (
      <>
        <div className="channel-title">{channel.title ?? channel.channelId}</div>
        <div className="channel-meta">ID: {channel.channelId}</div>
        {priceRange && <div className="channel-meta">Цена: {priceRange}</div>}
        {supplyRange && <div className="channel-meta">Supply: {supplyRange}</div>}
      </>
    );
  };

  return (
    <>
      <Modal
        open={open}
        onClose={onClose}
        title="Каналы"
        footer={
          <Button variant="secondary" onClick={() => setEditor(null)}>
            Добавить канал
          </Button>
        }
      >
        <div className="channels-list">
          {loading && <div className="channel-empty">Загружаю…</div>}
          {!loading && channels.length === 0 && <div className="channel-empty">Каналов нет</div>}
          {channels.map((channel) => (
            <div key={channel.id} className="channel-item">
              <button
                type="button"
                className="channel-info"
                onClick={() => setEditor(channel)}
              >
                {describeChannel(channel)}
              </button>
              <div className="channel-actions">
                <Button size="sm" variant="danger" onClick={() => setConfirm(channel)}>
                  Удалить
                </Button>
              </div>
            </div>
          ))}
        </div>
      </Modal>
      <ConfirmDialog
        open={Boolean(confirm)}
        title="Удалить канал?"
        message={`«${confirm?.title ?? confirm?.channelId}» будет удалён.`}
        onCancel={() => setConfirm(null)}
        onConfirm={handleDelete}
        confirmLabel="Удалить"
      />
      <EditChannelModal
        open={editor !== undefined}
        initial={editor ?? null}
        onClose={() => setEditor(undefined)}
        onSaved={() => {
          setEditor(undefined);
          void load();
        }}
      />
    </>
  );
};
