// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";
import lottie from "lottie-web";
import { Button } from "../../shared/ui/button/Button";
import { Skeleton } from "../../shared/ui/skeleton/Skeleton";
import { showError } from "../../shared/ui/feedback/toast";
import { listGifts, refreshGifts, getGiftsSettings, setGiftsSettings } from "../../entities/gifts/api";
import { listAccounts } from "../../entities/accounts/api";
import { getSettings } from "../../entities/settings/api";
import type { Gift } from "../../entities/gifts/model";
import type { Account } from "../../entities/accounts/model";
import { useOnScreen } from "../../shared/lib/hooks/useOnScreen";
import { openCentered } from "../../shared/lib/utils/openCentered";
import { usePopupAutoSize } from "../../shared/lib/hooks/usePopupAutoSize";
import { BuyGiftModal } from "./BuyGiftModal";
import "./gifts.css";

const TGS_CACHE = new Map<string, unknown>();
const GIFTS_DEBUG = true;
const dbg = (...args: unknown[]) => {
  if (GIFTS_DEBUG) console.log("[Gifts]", ...args);
};

const priceFormat = (value: number | null | undefined) =>
  typeof value === "number" ? value.toLocaleString("ru-RU") : value ?? "—";

const lockDateFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const parseIsoToDate = (value: string | null | undefined): Date | null => {
  if (!value) {
    return null;
  }
  const text = value.trim();
  if (!text) {
    return null;
  }
  const normalized = text.endsWith("Z") ? `${text.slice(0, -1)}+00:00` : text;
  const timestamp = Date.parse(normalized);
  if (Number.isNaN(timestamp)) {
    return null;
  }
  return new Date(timestamp);
};

const formatRelativeTime = (date: Date): string => {
  const diffMs = date.getTime() - Date.now();
  if (Number.isNaN(diffMs)) {
    return "—";
  }
  if (diffMs <= 0) {
    return "доступен";
  }
  const totalSeconds = Math.floor(diffMs / 1000);
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const parts: string[] = [];
  if (days > 0) parts.push(`${days}д`);
  if (hours > 0) parts.push(`${hours}ч`);
  if (minutes > 0) parts.push(`${minutes}м`);
  if (parts.length === 0) parts.push(`${seconds}с`);
  return `через ${parts.join(" ")}`;
};

const getAvailableAmount = (gift: Gift): number | null => {
  if (gift.availableAmount != null) return gift.availableAmount;
  if (gift.perUserAvailable != null) return gift.perUserAvailable;
  if (gift.perUserRemains != null) return gift.perUserRemains;
  return null;
};

const isGiftBuyable = (gift: Gift): boolean => {
  if (!gift.isLimited) {
    return true;
  }
  const available = getAvailableAmount(gift);
  return (available ?? 0) > 0;
};

const sortKeyForGift = (gift: Gift): [number, number, number, number, number] => {
  const buyablePriority = isGiftBuyable(gift) ? 0 : 1;
  const limitedPriority = gift.isLimited ? 0 : 1;
  const supplyPriority = gift.isLimited
    ? getAvailableAmount(gift) ?? Number.MAX_SAFE_INTEGER
    : gift.supply ?? Number.MAX_SAFE_INTEGER;
  const pricePriority = typeof gift.price === "number" ? gift.price : Number.MAX_SAFE_INTEGER;
  const idPriority = Number.isFinite(Number(gift.id)) ? Number(gift.id) : Number.MAX_SAFE_INTEGER;
  return [buyablePriority, limitedPriority, supplyPriority, pricePriority, idPriority];
};

interface TgsThumbProps {
  gift: Gift;
  onMissingToken: () => void;
}

const TgsThumb: React.FC<TgsThumbProps> = ({ gift, onMissingToken }) => {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const animationRef = React.useRef<ReturnType<typeof lottie.loadAnimation> | null>(null);
  const visible = useOnScreen(containerRef, "200px"); // Уменьшаем с 600px до 200px для меньшей нагрузки
  const [hasPlayed, setHasPlayed] = React.useState(false);

  const handleMouseEnter = React.useCallback(() => {
    if (animationRef.current && hasPlayed) {
      animationRef.current.goToAndPlay(0, true);
    }
  }, [hasPlayed]);

  React.useEffect(() => {
    const fileId = gift.stickerFileId;
    const uniq = gift.stickerUniqueId;
    
    if (!visible) {
      if (animationRef.current) {
        animationRef.current.pause();
      }
      dbg("thumb.pause", { id: gift.id });
      return;
    }
    
    if (visible && animationRef.current) {
      animationRef.current.play();
      dbg("thumb.resume", { id: gift.id });
      return;
    }
    
    if (!fileId && !uniq || !containerRef.current) {
      dbg("thumb.skip", { id: gift.id, visible, fileId: !!fileId, uniq: !!uniq });
      return;
    }
    dbg("thumb.start", { id: gift.id, visible, fileId, uniq });
    const containerElement = containerRef.current;
    if (!containerElement) {
      return;
    }
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
            if (TGS_CACHE.size > 50) {
              const [firstKey] = TGS_CACHE.keys();
              if (firstKey) TGS_CACHE.delete(firstKey);
            }
            return json;
          })());
        if (cancelled || !containerElement.isConnected) {
          return;
        }
        if (animationRef.current) {
          try {
            animationRef.current.destroy();
          } catch (err) {
            console.warn("Lottie destroy failed (re-init)", err);
            try {
              containerElement.innerHTML = "";
            } catch (clearError) {
              console.warn("[Gifts] Failed to reset container after destroy", clearError);
            }
          }
        }
        try {
          containerElement.innerHTML = "";
        } catch (clearError) {
          console.warn("[Gifts] Failed to reset container", clearError);
        }
        dbg("thumb.loadAnimation", { id: gift.id });
        const animation = lottie.loadAnimation({
          container: containerElement,
          renderer: "canvas", 
          loop: false,
          autoplay: true,
          animationData: data,
          rendererSettings: {
            preserveAspectRatio: "xMidYMid meet",
            progressiveLoad: true, 
            clearCanvas: true,
          },
        });
        
        animation.addEventListener("complete", () => {
          setHasPlayed(true);
        });
        
        animationRef.current = animation;
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
            containerElement.innerHTML = "";
          } catch (clearError) {
            console.warn("[Gifts] Failed to clear container during cleanup", clearError);
          }
        } finally {
          animationRef.current = null;
        }
      }
    };
  }, [gift.id, gift.stickerFileId, gift.stickerUniqueId, visible, onMissingToken]);

  return <div ref={containerRef} className="gift-thumb" onMouseEnter={handleMouseEnter} />;
};

interface GiftCardProps {
  gift: Gift;
  onMissingToken: () => void;
  onBuy: (gift: Gift) => void;
  disabled?: boolean;
}

const GiftCard: React.FC<GiftCardProps> = ({ gift, onMissingToken, onBuy, disabled }) => {
  const available = getAvailableAmount(gift);
  const totalSupply = gift.totalAmount ?? gift.supply;
  const limitedDescription = gift.isLimited
    ? `Доступно: ${
        available != null ? available.toLocaleString("ru-RU") : "?"
      }${typeof totalSupply === "number" ? ` из ${totalSupply.toLocaleString("ru-RU")}` : ""}`
    : "Без лимита";
  const perAccountLimit =
    gift.isLimited && gift.limitedPerUser
      ? `Лимит на аккаунт: ${(
          gift.perUserRemains ?? gift.perUserAvailable ?? 0
        ).toLocaleString("ru-RU")}`
      : null;
  const lockEntries = React.useMemo(() => {
    const entries: { accountId: number; formatted: string; relative: string }[] = [];
    const locks = gift.locks ?? {};
    Object.entries(locks).forEach(([accountKey, rawValue]) => {
      if (!rawValue) return;
      const date = parseIsoToDate(rawValue);
      if (!date) return;
      const accountId = Number(accountKey);
      if (!Number.isFinite(accountId)) return;
      entries.push({
        accountId,
        formatted: lockDateFormatter.format(date),
        relative: formatRelativeTime(date),
      });
    });
    entries.sort((a, b) => a.accountId - b.accountId);
    return entries;
  }, [gift.locks]);
  const buyDisabled = !isGiftBuyable(gift) || Boolean(disabled);

  return (
    <div className="gift-card">
      <TgsThumb gift={gift} onMissingToken={onMissingToken} />
      <div className="gift-card__header">
        <div className="gift-card__meta">#{gift.id}</div>
        <div className="gift-card__meta">Цена: {priceFormat(gift.price)}</div>
        <div className="gift-card__meta">{limitedDescription}</div>
        {perAccountLimit && <div className="gift-card__meta">{perAccountLimit}</div>}
        {gift.requiresPremium && <div className="gift-card__meta">Требует Premium</div>}
      </div>
      {lockEntries.length > 0 && (
        <div className="gift-card__locks">
          <div className="gift-card__locks-title">Локи</div>
          {lockEntries.map((lock) => (
            <div key={lock.accountId} className="gift-card__lock-item">
              <strong>{lock.accountId}</strong>: {lock.formatted} ({lock.relative})
            </div>
          ))}
        </div>
      )}
      <Button className="gift-card__buy" onClick={() => onBuy(gift)} disabled={buyDisabled}>
        Купить
      </Button>
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
  
  // Останавливаем все анимации при скрытии вкладки для экономии ресурсов
  React.useEffect(() => {
    const handleVisibilityChange = () => {
      const isHidden = document.hidden;
      dbg("visibilityChange", { hidden: isHidden });
      // Lottie автоматически обрабатывает visibility через requestAnimationFrame,
      // но мы можем дополнительно логировать
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);
  const [gifts, setGifts] = React.useState<Gift[]>([]);
  const [autoRefresh, setAutoRefresh] = React.useState(false);
  const [hasAccounts, setHasAccounts] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [missingToken, setMissingToken] = React.useState(false);
  const [accounts, setAccounts] = React.useState<Account[]>([]);
  const [selectedGift, setSelectedGift] = React.useState<Gift | null>(null);

  const sortedGifts = React.useMemo(() => {
    const items = [...gifts];
    items.sort((a, b) => {
      const aKey = sortKeyForGift(a);
      const bKey = sortKeyForGift(b);
      for (let i = 0; i < aKey.length; i += 1) {
        if (aKey[i] !== bKey[i]) {
          return aKey[i] - bKey[i];
        }
      }
      return 0;
    });
    return items;
  }, [gifts]);

  const handleOpenBuy = React.useCallback((gift: Gift) => {
    setSelectedGift(gift);
  }, []);

  const handleCloseBuy = React.useCallback(() => {
    setSelectedGift(null);
  }, []);

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
        const userSettings = await getSettings();
        dbg("api.getSettings", { hasBotToken: Boolean(userSettings.botToken) });
        setMissingToken(!userSettings.botToken);
      } catch (error) {
        console.warn("Failed to load settings", error);
      }
    })();
    (async () => {
      try {
        const fetched = await listAccounts();
        dbg("api.listAccounts", { count: fetched.length });
        setAccounts(fetched);
        setHasAccounts(fetched.length > 0);
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
      const refreshedItems = Array.isArray(data.items) ? data.items : [];
      dbg("api.refreshGifts", { ok: refreshedItems.length > 0, count: refreshedItems.length });
      if (refreshedItems.length > 0) {
        const items = refreshedItems.filter((gift) => gift.stickerFileId);
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
        {sortedGifts.length === 0 && !loading && <div className="gift-empty">Подарков нет</div>}
        {sortedGifts.length === 0 && loading && (
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
        {sortedGifts.map((gift) => (
          <GiftCard
            key={gift.id}
            gift={gift}
            onMissingToken={() => setMissingToken(true)}
            onBuy={handleOpenBuy}
            disabled={!hasAccounts}
          />
        ))}
      </div>
      <BuyGiftModal
        open={Boolean(selectedGift)}
        gift={selectedGift}
        accounts={accounts}
        onClose={handleCloseBuy}
        onPurchased={loadGifts}
      />
    </div>
  );
};
