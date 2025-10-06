# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import asyncio
import random
from typing import Any

import httpx
from sqlalchemy.orm import Session, joinedload

from ..db import SessionLocal
from ..logger import logger
from ..models import Account, Channel, User, UserSettings
from .tg_clients_service import tg_call

INF_SUPPLY = 10**12  # псевдо-бесконечность для сравнений/сортировок


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _per_user_cap(g: dict) -> int:
    try:
        if not bool(g.get("limited_per_user")):
            return INF_SUPPLY
        v = _int_or_none(g.get("per_user_available"))
        if v is None:
            v = _int_or_none(g.get("per_user_remains"))
        return max(0, v) if v is not None else 0
    except Exception:
        return 0


def _ival_ok(v: int | None, lo: int | None, hi: int | None) -> bool:
    # для матчей supply==None считаем невалидным (анлимиты мы вообще скипаем до матчей)
    if v is None:
        return False
    if lo is not None and v < lo:
        return False
    if hi is not None and v > hi:
        return False
    return True


def _gift_supply_raw(g: dict) -> int | None:
    try:
        value = _int_or_none(g.get("total_amount"))
        return value
    except Exception:
        return None


def _gift_avail(g: dict) -> int:
    try:
        value = _int_or_none(g.get("available_amount"))
        return value if value is not None else 0
    except Exception:
        return 0


def _gift_price(g: dict) -> int:
    try:
        value = _int_or_none(g.get("price"))
        return value if value is not None else 0
    except Exception:
        return 0


def _sort_key(g: dict) -> tuple[int, int, float]:
    # сортируем по supply (меньше — выше), затем по цене (дороже — выше), затем случайно
    sup = _gift_supply_raw(g)
    sup_for_sort = sup if sup is not None else INF_SUPPLY
    return (sup_for_sort, -_gift_price(g), random.random())


async def _stars_for(acc: Account) -> int:
    try:
        bal = await tg_call(
            acc.session_path,
            acc.api_profile.api_id,
            acc.api_profile.api_hash,
            lambda c: c.get_stars_balance(),
            min_interval=0.5,
        )
        return int(bal or 0)
    except Exception:
        logger.debug(f"autobuy:balance fail acc_id={acc.id}", exc_info=True)
        return 0


def _parse_error_reason(e: Exception) -> dict:
    return {"code": type(e).__name__, "message": str(e)[:400]}


async def _buy_with(acc: Account, chat_id: int, gift_id: int) -> tuple[bool, dict | None]:
    async def _call(c):
        return await c.send_gift(chat_id=int(chat_id), gift_id=int(gift_id))

    try:
        res = await tg_call(
            acc.session_path,
            acc.api_profile.api_id,
            acc.api_profile.api_hash,
            _call,
            min_interval=0.7,
        )
        logger.info(
            "autobuy:buy ok acc_id=%s chat_id=%s gift_id=%s res=%s",
            acc.id,
            chat_id,
            gift_id,
            type(res).__name__,
        )
        return True, None
    except Exception as e:
        reason = _parse_error_reason(e)
        logger.warning(
            "autobuy:buy fail acc_id=%s chat_id=%s gift_id=%s reason=%s msg=%s",
            acc.id,
            chat_id,
            gift_id,
            reason.get("code"),
            reason.get("message"),
            exc_info=True,
        )
        return False, reason


def _init_stats(chans: list[Channel], accs: list[Account]) -> dict:
    return {
        "channels": {
            int(c.channel_id): {
                "row_id": c.id,
                "purchased": [],  # [{gift_id, price, supply, account_id, channel_id}]
                "failed": [],  # [{gift_id, price, account_id, reason, rpc, channel_id}]
                "reasons": [],  # недостаток баланса и т.п.
                "planned": 0,
            }
            for c in chans
        },
        "accounts": {
            a.id: {
                "balance_start": 0,
                "balance_end": 0,
                "spent": 0,
                "purchases": 0,
                "planned": 0,
            }
            for a in accs
        },
        "global_skips": [],  # [{gift_id, reason, details?}]
        "plan_skips": [],  # [{gift_id, reason, details?}]
        "plan": [],  # [{account_id, channel_id, gift_id, price, supply}]
    }


def _channel_match(g: dict, ch: Channel) -> bool:
    s = _gift_supply_raw(g)
    p = _gift_price(g)
    return _ival_ok(s, ch.supply_min, ch.supply_max) and _ival_ok(p, ch.price_min, ch.price_max)


def _best_channel_for_gift(g: dict, chans: list[Channel]) -> Channel | None:
    xs = [ch for ch in chans if _channel_match(g, ch)]
    if not xs:
        return None
    xs.sort(
        key=lambda ch: (
            (ch.supply_max or INF_SUPPLY) - (ch.supply_min or 0),
            -(ch.price_max or 0),
            ch.id,
        )
    )
    return xs[0]


async def _dm_targets(user_id: int) -> tuple[str, list[int]]:
    db: Session = SessionLocal()
    try:
        s = db.get(UserSettings, user_id)
        token = (getattr(s, "bot_token", "")).strip() if s and getattr(s, "bot_token", None) else ""
        accs = (
            db.query(Account)
            .options(joinedload(Account.api_profile))
            .filter(Account.user_id == user_id)
            .all()
        )
    finally:
        db.close()
    if not token:
        return "", []
    ids: set[int] = set()
    for a in accs:
        try:
            me = await tg_call(
                a.session_path,
                a.api_profile.api_id,
                a.api_profile.api_hash,
                lambda c: c.get_me(),
                min_interval=0.5,
            )
            tid = int(getattr(me, "id", 0) or 0)
            if tid > 0:
                ids.add(tid)
        except Exception:
            logger.debug(f"autobuy:dm get_me fail acc_id={a.id}", exc_info=True)
        await asyncio.sleep(0.05)
    return token, sorted(ids)


def _build_lines_report(stats: dict, considered: list[dict]) -> list[str]:
    h = "🧾"
    ok = "✅"
    sk = "⏭️"
    no = "❌"
    star = "⭐"
    box = "📦"
    ch = "🛰️"
    acc = "👤"
    coin = "💰"
    chart = "📊"

    # купленные по gift_id
    pmap: dict[int, list[dict]] = {}
    for cid, pc in (stats.get("channels") or {}).items():
        for it in pc.get("purchased", []):
            gid = int(it.get("gift_id") or 0)
            pmap.setdefault(gid, []).append(it | {"channel_id": int(cid)})

    # ошибки/причины по каналам
    fail_by_gift: dict[int, list[dict]] = {}
    rsn_by_gift: dict[int, list[dict]] = {}
    for cid, chs in (stats.get("channels") or {}).items():
        for it in chs.get("failed", []):
            gid = int(it.get("gift_id") or 0)
            fail_by_gift.setdefault(gid, []).append({"cid": int(cid), **it})
        for it in chs.get("reasons", []):
            gid = int(it.get("gift_id") or 0)
            rsn_by_gift.setdefault(gid, []).append({"cid": int(cid), **it})

    # глобальные скипы
    gskip: dict[int, dict] = {}
    for it in stats.get("global_skips") or []:
        gskip[int(it.get("gift_id") or 0)] = it

    # план скипы (не хватило баланса на аккаунте, не матчится ни один канал и тп)
    plan_by_gift: dict[int, list[dict]] = {}
    for it in stats.get("plan_skips") or []:
        gid = int(it.get("gift_id") or 0)
        plan_by_gift.setdefault(gid, []).append(it)

    lines: list[str] = []
    lines.append(f"{h} Отчёт автопокупки")

    total = len(considered)
    bought = sum(len(v) for v in pmap.values())
    skipped = total - bought
    lines.append(f"{chart} Новых: {total} | Куплено: {bought} | Пропущено: {skipped}")

    if stats.get("plan_skips"):
        lines.append(f"{sk} Пропуски на этапе планирования: {len(stats['plan_skips'])}")

    lines.append("")
    lines.append(f"{box} По подаркам:")

    for g in considered:
        gid = int(g.get("id") or 0)
        price = _gift_price(g)
        sup_raw = _gift_supply_raw(g)
        sup_str = "∞" if sup_raw is None else str(sup_raw)
        avail = g.get("available_amount")

        if gid in pmap:
            for it in pmap[gid]:
                line = (
                    f"• {ok} {gid} | {price}{star} | supply={sup_str} "
                    f"→ ch={it.get('channel_id')} acc={it.get('account_id')}"
                )
                lines.append(line)
            continue

        # глобальный скип (например unlimited)
        if gid in gskip:
            r = gskip[gid]
            det = r.get("details")
            s = f"• {sk} {gid} | {price}{star} | supply={sup_str} → {r.get('reason')}"
            if det:
                s += f" [{', '.join(map(str, det))}]"
            lines.append(s)
            continue

        any_line = False

        if gid in rsn_by_gift:
            any_line = True
            lines.append(f"• {no} {gid} | {price}{star} | supply={sup_str}")
            for x in rsn_by_gift[gid][:5]:
                reason_line = (
                    f"   — причина ch={x['cid']}: {x.get('reason')} "
                    f"acc={x.get('account_id')} bal={x.get('balance')} need={x.get('need')}"
                )
                lines.append(reason_line)

        if gid in fail_by_gift:
            if not any_line:
                lines.append(f"• {no} {gid} | {price}{star} | supply={sup_str}")
                any_line = True
            for x in fail_by_gift[gid][:5]:
                rpc = x.get("rpc")
                rpc_txt = (
                    f" ({rpc.get('code')} | {rpc.get('message')})" if isinstance(rpc, dict) else ""
                )
                error_line = (
                    f"   — ошибка ch={x['cid']}: send_gift_failed "
                    f"acc={x.get('account_id')}{rpc_txt}"
                )
                lines.append(error_line)

        if gid in plan_by_gift:
            if not any_line:
                lines.append(f"• {sk} {gid} | {price}{star} | supply={sup_str}")
                any_line = True
            for x in plan_by_gift[gid][:5]:
                det = x.get("details")
                lines.append(
                    f"   — план: {x.get('reason')}"
                    + (f" ({'; '.join(map(str, det))})" if det else "")
                )

        if not any_line and isinstance(avail, int) and avail <= 0:
            lines.append(
                f"• {sk} {gid} | {price}{star} | supply={sup_str} → not_available (avail=0)"
            )
            any_line = True

        if not any_line:
            lines.append(f"• {no} {gid} | {price}{star} | supply={sup_str} (нет данных)")

    lines.append("")
    lines.append(f"{ch} По каналам:")
    for cid, st in (stats.get("channels") or {}).items():
        lines.append(
            f"• {cid}: plan={st.get('planned', 0)} ok={len(st.get('purchased', []))} "
            f"fail={len(st.get('failed', []))} reasons={len(st.get('reasons', []))}"
        )

    lines.append("")
    lines.append(f"{acc} По аккаунтам:")
    for aid, st in (stats.get("accounts") or {}).items():
        lines.append(
            f"• acc={aid}: plan={st.get('planned', 0)} "
            f"{coin}spent={st.get('spent', 0)} start={st.get('balance_start', 0)} "
            f"end={st.get('balance_end', 0)} buys={st.get('purchases', 0)}"
        )

    tail = [x for x in (stats.get("plan_skips") or []) if int(x.get("gift_id") or 0) not in pmap]
    if tail:
        lines.append("")
        lines.append(f"{sk} Итого пропуски планирования: {len(tail)}")

    return lines


def _split_messages(lines: list[str], limit: int = 3800) -> list[str]:
    out = []
    cur: list[str] = []
    sz = 0
    for ln in lines:
        add = len(ln) + 1
        if sz + add > limit and cur:
            out.append("\n".join(cur))
            cur = [ln]
            sz = len(ln) + 1
        else:
            cur.append(ln)
            sz += add
    if cur:
        out.append("\n".join(cur))
    return out


async def _send_texts(token: str, chat_ids: list[int], msgs: list[str]) -> None:
    if not token or not chat_ids or not msgs:
        return
    base = f"https://api.telegram.org/bot{token}"
    async with httpx.AsyncClient(timeout=30) as http:
        for chat in chat_ids:
            for text in msgs:
                payload = {
                    "chat_id": int(chat),
                    "text": text,
                    "disable_web_page_preview": True,
                    "disable_notification": True,
                }
                try:
                    logger.info(
                        "autobuy:report send chat=%s size=%s",
                        chat,
                        len(text),
                    )
                    send_url = f"{base}/sendMessage"
                    r = await http.post(send_url, json=payload)
                    ok = r.status_code == 200 and r.json().get("ok", False)
                    if not ok:
                        logger.warning(
                            "autobuy:report send fail chat=%s code=%s body=%s",
                            chat,
                            r.status_code,
                            r.text[:200],
                        )
                except Exception:
                    logger.exception(
                        "autobuy:report http fail chat=%s",
                        chat,
                        exc_info=True,
                    )
                await asyncio.sleep(0.05)


# планирование
async def _plan_purchases(
    chans: list[Channel],
    accs: list[Account],
    gifts: list[dict],
    stars_left: dict[int, int],
    stats: dict,
    forced_cid: int | None = None,
) -> list[dict]:
    gifts_sorted = list(gifts or [])
    gifts_sorted.sort(key=_sort_key)
    budget = {a.id: stars_left.get(a.id, 0) for a in accs}
    remain_by_gift = {}
    for g in gifts_sorted:
        gid = int(g.get("id") or 0)
        if gid <= 0:
            continue
        remain_by_gift[gid] = max(0, _gift_avail(g))
    plan: list[dict] = []
    planned_by_acc_gid: dict[tuple[int, int], int] = {}

    for acc in sorted(accs, key=lambda a: budget.get(a.id, 0), reverse=True):
        bal = budget.get(acc.id, 0)
        if bal <= 0:
            continue

        for g in gifts_sorted:
            gid = int(g.get("id") or 0)
            price = _gift_price(g)
            sup_raw = _gift_supply_raw(g)
            if gid <= 0 or price <= 0:
                continue
            if remain_by_gift.get(gid, 0) <= 0:
                continue
            if forced_cid is not None:
                cid = int(forced_cid)
            else:
                ch = _best_channel_for_gift(g, chans)
                if not ch:
                    stats["plan_skips"].append(
                        {
                            "gift_id": gid,
                            "reason": "no_channel_match",
                            "details": [f"supply={sup_raw} price={price}"],
                        }
                    )
                    continue
                cid = int(ch.channel_id)

            cap_total = _per_user_cap(g)
            already = planned_by_acc_gid.get((acc.id, gid), 0)
            cap_left = max(0, cap_total - already)

            if cap_left <= 0:
                stats["plan_skips"].append(
                    {
                        "gift_id": gid,
                        "reason": "per_user_cap_reached",
                        "details": [f"acc={acc.id} cap={cap_total}"],
                    }
                )
                continue

            max_qty = min(remain_by_gift[gid], bal // price, cap_left)
            if max_qty <= 0:
                if bal < price:
                    stats["plan_skips"].append(
                        {
                            "gift_id": gid,
                            "reason": "not_enough_stars_account",
                            "details": [f"acc={acc.id} bal={bal} need={price}"],
                        }
                    )
                continue

            for _ in range(int(max_qty)):
                plan.append(
                    {
                        "account_id": acc.id,
                        "channel_id": cid,
                        "gift_id": gid,
                        "price": price,
                        "supply": sup_raw,
                    }
                )
                stats["channels"].setdefault(
                    cid,
                    {"row_id": None, "purchased": [], "failed": [], "reasons": [], "planned": 0},
                )
                stats["channels"][cid]["planned"] += 1
                stats["accounts"][acc.id]["planned"] += 1
                planned_by_acc_gid[(acc.id, gid)] = planned_by_acc_gid.get((acc.id, gid), 0) + 1
                bal -= price
                remain_by_gift[gid] -= 1
                if (
                    bal < price
                    or remain_by_gift[gid] <= 0
                    or planned_by_acc_gid[(acc.id, gid)] >= cap_total
                ):
                    break

        budget[acc.id] = bal

    head = ", ".join(f"{k}:{v}" for k, v in list(remain_by_gift.items())[:10])
    tail = " ..." if len(remain_by_gift) > 10 else ""
    logger.info(
        "autobuy:plan size=%s remain_gifts={ %s%s }",
        len(plan),
        head,
        tail,
    )
    stats["plan"] = plan
    return plan


async def _execute_plan(
    plan: list[dict], accs: list[Account], stats: dict, stars_left: dict[int, int]
) -> None:
    acc_by_id = {a.id: a for a in accs}
    for item in plan:
        aid = item["account_id"]
        cid = item["channel_id"]
        gid = item["gift_id"]
        price = item["price"]
        acc = acc_by_id.get(aid)
        bal = stars_left.get(aid, 0)

        if not acc:
            stats["channels"][cid]["failed"].append(
                {
                    "gift_id": gid,
                    "price": price,
                    "account_id": aid,
                    "reason": "account_missing",
                    "channel_id": cid,
                }
            )
            continue

        if bal < price:
            stats["channels"][cid]["reasons"].append(
                {
                    "gift_id": gid,
                    "reason": "insufficient_account_balance",
                    "account_id": aid,
                    "balance": bal,
                    "need": price,
                }
            )
            continue

        ok, rpc = await _buy_with(acc, cid, gid)
        if ok:
            stars_left[aid] = max(0, bal - price)
            stats["accounts"][aid]["spent"] += price
            stats["accounts"][aid]["purchases"] += 1
            stats["channels"][cid]["purchased"].append(
                {
                    "gift_id": gid,
                    "price": price,
                    "supply": item.get("supply"),
                    "account_id": aid,
                    "channel_id": cid,
                }
            )
        else:
            stats["channels"][cid]["failed"].append(
                {
                    "gift_id": gid,
                    "price": price,
                    "account_id": aid,
                    "reason": "send_gift_failed",
                    "rpc": rpc,
                    "channel_id": cid,
                }
            )


# сама покупка
async def autobuy_new_gifts(user_id: int, gifts: list[dict]) -> dict:
    db: Session = SessionLocal()
    try:
        u = db.get(User, user_id)
        if not u or not bool(getattr(u, "gifts_autorefresh", False)):
            logger.info("autobuy:skip user_id=%s reason=autorefresh_off", user_id)
            return {
                "purchased": [],
                "skipped": len(gifts or []),
                "stats": {
                    "channels": {},
                    "accounts": {},
                    "global_skips": [{"reason": "autorefresh_off"}],
                },
            }
        chans: list[Channel] = (
            db.query(Channel).filter(Channel.user_id == user_id).order_by(Channel.id.asc()).all()
        )
        accs: list[Account] = (
            db.query(Account)
            .options(joinedload(Account.api_profile))
            .filter(Account.user_id == user_id)
            .order_by(Account.id.asc())
            .all()
        )
        us = db.get(UserSettings, user_id)
        forced_cid = int(us.buy_target_id) if (us and us.buy_target_id is not None) else None
    finally:
        db.close()

    if not accs:
        logger.info("autobuy:skip user_id=%s reason=no_accounts", user_id)
        return {
            "purchased": [],
            "skipped": len(gifts or []),
            "stats": {"channels": {}, "accounts": {}, "global_skips": [{"reason": "no_accounts"}]},
        }

    if forced_cid is None and not chans:
        logger.info("autobuy:skip user_id=%s reason=no_channels", user_id)
        return {
            "purchased": [],
            "skipped": len(gifts or []),
            "stats": {"channels": {}, "accounts": {}, "global_skips": [{"reason": "no_channels"}]},
        }

    stats = _init_stats(chans, accs)
    if forced_cid is not None:
        stats["channels"].setdefault(
            int(forced_cid),
            {"row_id": None, "purchased": [], "failed": [], "reasons": [], "planned": 0},
        )

    stars_left: dict[int, int] = {}
    for a in accs:
        bal = await _stars_for(a)
        stars_left[a.id] = bal
        stats["accounts"][a.id]["balance_start"] = bal
    total_stars = sum(stars_left.values())
    details = ", ".join(f"{k}:{v}" for k, v in stars_left.items())
    logger.info(
        "autobuy:balances user_id=%s total=%s details={%s}",
        user_id,
        total_stars,
        details,
    )

    raw_items = list(gifts or [])
    considered_for_report = raw_items[:]

    for g in raw_items:
        gid = int(g.get("id") or 0)
        price = _gift_price(g)
        lim = bool(g.get("is_limited", False))
        sup_raw = _gift_supply_raw(g)
        if gid <= 0 or price <= 0:
            stats["global_skips"].append({"gift_id": gid, "reason": "invalid/price"})
            continue
        if not lim:
            stats["global_skips"].append({"gift_id": gid, "reason": "unlimited"})
            continue
        if sup_raw is None:
            stats["global_skips"].append({"gift_id": gid, "reason": "no_supply_for_limited"})
            continue

    items_for_plan = [
        g
        for g in raw_items
        if int(g.get("id") or 0) > 0
        and _gift_price(g) > 0
        and bool(g.get("is_limited", False)) is True
        and _gift_supply_raw(g) is not None
    ]
    items_for_plan.sort(key=_sort_key)

    plan = await _plan_purchases(
        chans, accs, items_for_plan, stars_left, stats, forced_cid=forced_cid
    )
    await _execute_plan(plan, accs, stats, stars_left)

    # финал
    purchased: list[dict] = []
    for cid, st in stats["channels"].items():
        for it in st["purchased"]:
            purchased.append(
                {
                    "gift_id": it["gift_id"],
                    "price": it["price"],
                    "supply": it.get("supply"),
                    "channel_id": cid,
                    "channel_row_id": st["row_id"],
                    "account_id": it["account_id"],
                }
            )

    for aid in stats["accounts"]:
        stats["accounts"][aid]["balance_end"] = stars_left.get(aid, 0)

    skipped = len(considered_for_report) - len(purchased)

    logger.info(
        "autobuy:summary user_id=%s purchased=%s skipped=%s plan=%s",
        user_id,
        len(purchased),
        skipped,
        len(plan),
    )
    for cid, st in stats["channels"].items():
        logger.info(
            "autobuy:channel cid=%s plan=%s ok=%s fail=%s reasons=%s",
            cid,
            st["planned"],
            len(st["purchased"]),
            len(st["failed"]),
            len(st["reasons"]),
        )
        if st["failed"]:
            logger.info(
                "autobuy:channel cid=%s failed_details=%s",
                cid,
                st["failed"][:5],
            )

    for aid, st in stats["accounts"].items():
        logger.info(
            "autobuy:account id=%s plan=%s spent=%s start=%s end=%s buys=%s",
            aid,
            st["planned"],
            st["spent"],
            st["balance_start"],
            st["balance_end"],
            st["purchases"],
        )

    if stats["global_skips"]:
        logger.info(
            "autobuy:global_skips n=%s details=%s",
            len(stats["global_skips"]),
            stats["global_skips"],
        )
    if stats["plan_skips"]:
        tail = " ..." if len(stats["plan_skips"]) > 10 else ""
        logger.info(
            "autobuy:plan_skips n=%s details=%s%s",
            len(stats["plan_skips"]),
            stats["plan_skips"][:10],
            tail,
        )

    # отчёт в лс
    try:
        token, dm_ids = await _dm_targets(user_id)
        if token and dm_ids:
            lines = _build_lines_report(stats, considered_for_report)
            msgs = _split_messages(lines)
            await _send_texts(token, dm_ids, msgs)
            logger.info(
                "autobuy:report sent dm=%s msgs=%s",
                len(dm_ids),
                len(msgs),
            )
        else:
            logger.info("autobuy:report skipped (no token or dm targets)")
    except Exception:
        logger.exception("autobuy:report failed", exc_info=True)

    return {"purchased": purchased, "skipped": skipped, "stats": stats}
