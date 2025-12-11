# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import asyncio
import re
from time import perf_counter

from sqlalchemy.orm import Session

from backend.infrastructure.db.models import Account, Channel
from backend.services.tg_clients_service import tg_call
from backend.shared.logging import logger

PROBE_CALL_TIMEOUT = 6.0


def norm_ch_id(v) -> int:
    s = str(v or "").strip()
    if not s:
        raise ValueError("invalid channel id")
    if s.startswith("-100"):
        tail = re.sub(r"\D", "", s[4:])
        if not tail:
            raise ValueError("invalid channel id")
        return int("-100" + tail)
    digits = re.sub(r"\D", "", s)
    if not digits:
        raise ValueError("invalid channel id")
    return int("-100" + digits)


def _status_joined(st) -> bool:
    s = str(st or "").lower()
    return "left" not in s and "kicked" not in s


def _int_or_none(v, name: str) -> int | None:
    if v is None:
        return None
    if isinstance(v, bool):
        raise ValueError(f"{name} must be integer")
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        t = v.strip()
        if t.lower() == "null":
            return None
        if t == "":
            raise ValueError(f"{name} must be integer")
        if re.fullmatch(r"[+-]?\d+", t):
            return int(t)
    raise ValueError(f"{name} must be integer")


def _coerce_range(lo_name: str, hi_name: str, lo, hi) -> tuple[int | None, int | None]:
    lo_i = _int_or_none(lo, lo_name)
    hi_i = _int_or_none(hi, hi_name)
    if lo_i is not None and hi_i is not None and lo_i > hi_i:
        raise ValueError(f"{lo_name} must be <= {hi_name}")
    return lo_i, hi_i


async def _safe_tg_call(acc: Account, fn, timeout: float):
    try:
        return await tg_call(
            acc.session_path,
            acc.api_profile.api_id,
            acc.api_profile.api_hash,
            fn,
            op_timeout=timeout,
        )
    except Exception as e:
        fn_name = getattr(fn, "__name__", "lambda")
        err_name = type(e).__name__
        logger.debug(
            f"channels.probe.call: err (acc_id={acc.id}, fn={fn_name}, {err_name})"
        )
        return None


def _probe_one_account(acc: Account, ch_id: int) -> tuple[str | None, bool]:
    async def work(timeout: float) -> tuple[str | None, bool]:
        title = None
        joined = False
        m = await _safe_tg_call(acc, lambda c: c.get_chat_member(ch_id, "me"), timeout)
        if m is not None:
            try:
                joined = _status_joined(getattr(m, "status", None))
            except Exception:
                joined = False
            try:
                chat_obj = getattr(m, "chat", None)
                if chat_obj and getattr(chat_obj, "title", None):
                    title = chat_obj.title
            except Exception:
                pass
        if not title:
            chat = await _safe_tg_call(acc, lambda c: c.get_chat(ch_id), timeout)
            if chat is not None and getattr(chat, "title", None):
                title = chat.title
        return title, joined

    t0 = perf_counter()
    try:
        title, joined = asyncio.run(work(PROBE_CALL_TIMEOUT))
        dt = (perf_counter() - t0) * 1000
        logger.info(
            "channels.probe: acc="
            f"{acc.id}, ch_id={ch_id}, title={'yes' if title else 'no'}, joined={int(joined)}, "
            f"dt_ms={dt:.0f}"
        )
        return title, joined
    except Exception:
        dt = (perf_counter() - t0) * 1000
        logger.warning(
            f"channels.probe: fail (acc_id={acc.id}, ch_id={ch_id}, dt_ms={dt:.0f}, err=Exception)"
        )
        return None, False


def _probe_any_account(
    db: Session, user_id: int, ch_id: int
) -> tuple[str | None, bool]:
    title = None
    any_joined = False
    accounts = (
        db.query(Account)
        .filter(Account.user_id == user_id)
        .order_by(Account.id.asc())
        .all()
    )
    if not accounts:
        logger.info(f"channels.probe: no_accounts (user_id={user_id})")
        return None, False
    for acc in accounts:
        t, j = _probe_one_account(acc, ch_id)
        if not title and t:
            title = t
        if j:
            any_joined = True
        break
    logger.info(
        f"channels.probe.summary: user_id={user_id}, ch_id={ch_id}, "
        f"title={'yes' if title else 'no'}, joined={int(any_joined)}"
    )
    return title, any_joined


def list_channels(db: Session, user_id: int) -> list[dict]:
    rows = (
        db.query(Channel)
        .filter(Channel.user_id == user_id)
        .order_by(Channel.id.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "channel_id": int(r.channel_id),
            "title": r.title,
            "price_min": r.price_min,
            "price_max": r.price_max,
            "supply_min": r.supply_min,
            "supply_max": r.supply_max,
        }
        for r in rows
    ]


def create_channel(
    db: Session,
    user_id: int,
    channel_id,
    price_min,
    price_max,
    supply_min,
    supply_max,
    title_input: str | None,
) -> dict:
    try:
        ch_id = norm_ch_id(channel_id)
    except ValueError:
        return {"error": "bad_channel_id"}
    try:
        price_min, price_max = _coerce_range(
            "price_min", "price_max", price_min, price_max
        )
        supply_min, supply_max = _coerce_range(
            "supply_min", "supply_max", supply_min, supply_max
        )
    except ValueError:
        return {
            "error": "bad_range",
            "context": {"fields": ["price_min", "price_max"]},
        }
    exists = (
        db.query(Channel.id)
        .filter(Channel.user_id == user_id, Channel.channel_id == ch_id)
        .first()
    )
    if exists:
        return {"error": "duplicate_channel"}
    probed_title, joined = _probe_any_account(db, user_id, ch_id)
    if not joined:
        return {"error": "channel_not_joined"}
    title = (title_input or "").strip() or (probed_title or None)
    ch = Channel(
        user_id=user_id,
        channel_id=ch_id,
        title=title,
        price_min=price_min,
        price_max=price_max,
        supply_min=supply_min,
        supply_max=supply_max,
    )
    db.add(ch)
    db.commit()
    return {"channel_id": ch.id}


def update_channel(db: Session, user_id: int, ch_id: int, **f) -> dict:
    ch = (
        db.query(Channel)
        .filter(Channel.id == ch_id, Channel.user_id == user_id)
        .first()
    )
    if not ch:
        return {"error": "not_found"}
    if "title" in f:
        t = (f["title"] or "").strip()
        f["title"] = t or None
    if "price_min" in f or "price_max" in f:
        try:
            lo, hi = _coerce_range(
                "price_min",
                "price_max",
                f.get("price_min", ch.price_min),
                f.get("price_max", ch.price_max),
            )
        except ValueError:
            return {
                "error": "bad_range",
                "context": {"fields": ["price_min", "price_max"]},
            }
        f["price_min"], f["price_max"] = lo, hi
    if "supply_min" in f or "supply_max" in f:
        try:
            lo, hi = _coerce_range(
                "supply_min",
                "supply_max",
                f.get("supply_min", ch.supply_min),
                f.get("supply_max", ch.supply_max),
            )
        except ValueError:
            return {
                "error": "bad_range",
                "context": {"fields": ["supply_min", "supply_max"]},
            }
        f["supply_min"], f["supply_max"] = lo, hi
    for k in ("title", "price_min", "price_max", "supply_min", "supply_max"):
        if k in f:
            setattr(ch, k, f[k])
    db.commit()
    return {"ok": True}


def delete_channel(db: Session, user_id: int, ch_id: int) -> dict:
    ch = (
        db.query(Channel)
        .filter(Channel.id == ch_id, Channel.user_id == user_id)
        .first()
    )
    if not ch:
        return {"error": "not_found"}
    db.delete(ch)
    db.commit()
    return {"ok": True}
