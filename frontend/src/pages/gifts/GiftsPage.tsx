// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import lottie from "lottie-web";
import { Button } from "../../shared/ui/button/Button";
import { Skeleton } from "../../shared/ui/skeleton/Skeleton";
import { showError } from "../../shared/ui/feedback/toast";
import { listGifts, refreshGifts, getGiftsSettings, setGiftsSettings } from "../../entities/gifts/api";
import { listAccounts } from "../../entities/accounts/api";
import type { Gift } from "../../entities/gifts/model";
import { useOnScreen } from "../../shared/lib/hooks/useOnScreen";
import { openCentered } from "../../shared/lib/utils/openCentered";
import { usePopupAutoSize } from "../../shared/lib/hooks/usePopupAutoSize";
import "./gifts.css";

const TGS_CACHE = new Map<string, unknown>();
const GIFTS_DEBUG = true;
const dbg = (...args: unknown[]) => {
  if (GIFTS_DEBUG) console.log("[Gifts]", ...args);
};

const priceFormat = (value: number | null | undefined) =>
  typeof value === "number" ? value.toLocaleString("ru-RU") : value ?? "—";

interface TgsThumbProps {
  gift: Gift;
  onMissingToken: () => void;
}

const TgsThumb: React.FC<TgsThumbProps> = ({ gift, onMissingToken }) => {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const animationRef = React.useRef<ReturnType<typeof lottie.loadAnimation> | null>(null);
  const visible = useOnScreen(containerRef, "600px");

  React.useEffect(() => {
    const fileId = gift.stickerFileId;
    const uniq = gift.stickerUniqueId;
    if (!visible || (!fileId && !uniq) || !containerRef.current) {
      dbg("thumb.skip", { id: gift.id, visible, fileId: !!fileId, uniq: !!uniq });
      return;
    }
    dbg("thumb.start", { id: gift.id, visible, fileId, uniq });
    const params = new URLSearchParams();
    if (fileId) params.set("file_id", fileId);
    if (uniq) params.set("uniq", uniq);
    const src = `/api/gifts/sticker.lottie?${params.toString()}`;

    let cancelled = false;
    const controller = new AbortController();

    (async () => {
      try {
        const cached = TGS_CACHE.get(src);
        const data =
          cached ??
          (await (async () => {
            const response = await fetch(src, { credentials: "include", signal: controller.signal });
            if (response.status === 409) {
              const body = await response.json().catch(() => ({}));
              if ((body as { error?: string }).error === "no_bot_token") {
                dbg("thumb.no_bot_token", { id: gift.id });
                onMissingToken();
              }
              throw new Error("no_bot_token");
            }
            if (!response.ok) {
              throw new Error(`HTTP ${response.status}`);
            }
            const json = await response.json();
            TGS_CACHE.set(src, json);
            if (TGS_CACHE.size > 30) {
              const [firstKey] = TGS_CACHE.keys();
              if (firstKey) TGS_CACHE.delete(firstKey);
            }
            return json;
          })());
        if (cancelled || !containerRef.current) {
          return;
        }
        if (animationRef.current) {
          try {
            animationRef.current.destroy();
          } catch (err) {
            console.warn("Lottie destroy failed (re-init)", err);
            try {
              if (containerRef.current) containerRef.current.innerHTML = "";
            } catch {}
          }
        }
        try {
          if (containerRef.current) containerRef.current.innerHTML = "";
        } catch {}
        dbg("thumb.loadAnimation", { id: gift.id });
        animationRef.current = lottie.loadAnimation({
          container: containerRef.current,
          renderer: "svg",
          loop: true,
          autoplay: true,
          animationData: data,
          rendererSettings: {
            preserveAspectRatio: "xMidYMid meet",
            progressiveLoad: false,
            hideOnTransparent: true,
          },
        });
      } catch (error) {
        console.warn("[Gifts] Lottie load failed", error);
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
      if (animationRef.current) {
        dbg("thumb.cleanup", { id: gift.id });
        try {
          animationRef.current.destroy();
        } catch (err) {
          console.warn("[Gifts] Lottie destroy failed (cleanup)", err);
          try {
            if (containerRef.current) containerRef.current.innerHTML = "";
          } catch {}
        } finally {
          animationRef.current = null;
        }
      }
    };
  }, [gift.stickerFileId, gift.stickerUniqueId, visible, onMissingToken]);

  return <div ref={containerRef} className="gift-thumb" />;
};

const GiftCard: React.FC<{ gift: Gift; onMissingToken: () => void }> = ({ gift, onMissingToken }) => {
  const limited = gift.isLimited
    ? `Лимит: ${gift.availableAmount != null ? gift.availableAmount : "?"}`
    : "Без лимита";
  return (
    <div className="gift-card">
      <TgsThumb gift={gift} onMissingToken={onMissingToken} />
      <div className="gift-card__meta">#{gift.id}</div>
      <div className="gift-card__meta">Цена: {priceFormat(gift.price)}</div>
      <div className="gift-card__meta">{limited}</div>
      {gift.requiresPremium && <div className="gift-card__meta">Требует Premium</div>}
    </div>
  );
};

export const GiftsPage: React.FC = () => {
  const [isPopup, setIsPopup] = React.useState(false);
  React.useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const flag = params.get("popup");
    const opener = Boolean((window as Window).opener);
    const popup = Boolean(opener || flag);
    setIsPopup(popup);
    dbg("init.isPopup", {
      popup,
      opener,
      query: Boolean(flag),
      search: window.location.search,
      win: { w: window.innerWidth, h: window.innerHeight, dpr: window.devicePixelRatio },
    });
  }, []);
  usePopupAutoSize(isPopup);
  const [gifts, setGifts] = React.useState<Gift[]>([]);
  const [autoRefresh, setAutoRefresh] = React.useState(false);
  const [hasAccounts, setHasAccounts] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [missingToken, setMissingToken] = React.useState(false);

  const loadGifts = React.useCallback(async () => {
    try {
      const data = await listGifts();
      dbg("api.listGifts", { total: data.length });
      const items = data.filter((gift) => gift.stickerFileId);
      dbg("state.setGifts", { withSticker: items.length });
      setGifts(items);
    } catch (error) {
      showError(error, "Не удалось загрузить подарки");
    }
  }, []);


  React.useEffect(() => {
    void loadGifts();
    (async () => {
      try {
        const settings = await getGiftsSettings();
        dbg("api.getGiftsSettings", settings);
        setAutoRefresh(settings.autoRefresh);
      } catch (error) {
        console.warn("Failed to load gifts settings", error);
      }
    })();
    (async () => {
      try {
        const accounts = await listAccounts();
        dbg("api.listAccounts", { count: accounts.length });
        setHasAccounts(accounts.length > 0);
      } catch (error) {
        console.warn("Failed to check accounts", error);
      }
    })();
  }, [loadGifts]);

  const handleRefresh = React.useCallback(async () => {
    if (loading || !hasAccounts) return;
    setLoading(true);
    try {
      const data = await refreshGifts();
      dbg("api.refreshGifts", { ok: Array.isArray((data as any).items), count: Array.isArray((data as any).items) ? (data as any).items.length : undefined });
      if (Array.isArray(data.items)) {
        const items = data.items.filter((gift) => gift.stickerFileId);
        dbg("state.setGifts", { withSticker: items.length });
        setGifts(items);
      } else {
        await loadGifts();
      }
    } catch (error) {
      showError(error, "Ошибка обновления подарков");
    } finally {
      setLoading(false);
    }
  }, [hasAccounts, loadGifts, loading]);

  const toggleAuto = React.useCallback(async () => {
    if (!hasAccounts) return;
    const next = !autoRefresh;
    dbg("ui.toggleAutoRefresh", { next });
    setAutoRefresh(next);
    try {
      await setGiftsSettings(next);
    } catch (error) {
      setAutoRefresh(!next);
      showError(error, "Не удалось сохранить настройку");
    }
  }, [autoRefresh, hasAccounts]);

  React.useEffect(() => {
    if (!autoRefresh || !hasAccounts) return;
    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    const schedule = () => {
      if (cancelled) return;
      timeoutId = setTimeout(async () => {
        if (document.hidden) {
          schedule();
          return;
        }
        await handleRefresh();
        schedule();
      }, 30000);
    };
    schedule();
    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [autoRefresh, hasAccounts, handleRefresh]);

  return (
    <div className={`gifts-page${isPopup ? " is-popup" : ""}`}>
      {missingToken && (
        <div className="gift-alert">
          <span>Нет Bot token. Укажите его в настройках, чтобы загрузить превью.</span>
          <Button variant="secondary" onClick={() => openCentered("/settings?popup=1", "settings", 520, 420)}>
            Открыть настройки
          </Button>
        </div>
      )}
      <div className="gifts-header">
        <h1>Подарки</h1>
        {hasAccounts && (
          <div className="gifts-actions">
            <label className="switch">
              <input type="checkbox" checked={autoRefresh} onChange={toggleAuto} />
              <span className="switch__track">
                <span className="switch__thumb" />
              </span>
              <span className="switch__text">Автообновление</span>
            </label>
            <Button onClick={handleRefresh} loading={loading} disabled={loading}>
              {loading ? "Обновляю…" : "Обновить"}
            </Button>
          </div>
        )}
      </div>
      <div className="gifts-grid">
        {gifts.length === 0 && !loading && <div className="gift-empty">Подарков нет</div>}
        {gifts.length === 0 && loading && (
          <>
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="gift-card">
                <Skeleton height={120} />
                <Skeleton height={12} width="70%" />
                <Skeleton height={12} width="40%" />
              </div>
            ))}
          </>
        )}
        {gifts.map((gift) => (
          <GiftCard key={gift.id} gift={gift} onMissingToken={() => setMissingToken(true)} />
        ))}
      </div>
    </div>
  );
};
