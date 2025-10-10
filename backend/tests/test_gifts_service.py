# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from backend.services import gifts_service


@pytest.mark.asyncio
async def test_deferred_autobuy_task_cleans_up(monkeypatch: pytest.MonkeyPatch) -> None:
    uid = 777
    gift_id = 42
    account_id = 555
    run_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    calls: list[tuple[int, list[dict]]] = []

    async def fake_autobuy(user_id: int, gifts: list[dict]) -> dict:
        calls.append((user_id, gifts))
        return {"purchased": [], "skipped": len(gifts), "stats": {}, "deferred": []}

    def fake_read_json(path: str) -> list[dict]:  # noqa: ARG001 - path is unused in stub
        return [{"id": gift_id}]

    monkeypatch.setattr(gifts_service, "autobuy_new_gifts", fake_autobuy)
    monkeypatch.setattr(gifts_service, "read_json_list_of_dicts", fake_read_json)

    gifts_service._DEFERRED_TASKS.pop(uid, None)  # ensure clean state

    gifts_service._schedule_deferred_runs(
        uid,
        [
            {
                "gift_id": gift_id,
                "account_id": account_id,
                "run_at": run_at,
            }
        ],
    )

    tasks = gifts_service._DEFERRED_TASKS.get(uid)
    assert tasks is not None
    task = tasks.get((gift_id, account_id))
    assert task is not None

    await task

    assert not task.cancelled()
    assert task.exception() is None
    assert calls == [(uid, [{"id": gift_id}])]
    assert (gift_id, account_id) not in gifts_service._DEFERRED_TASKS.get(uid, {})

    # cleanup to avoid leaking tasks between tests
    gifts_service._DEFERRED_TASKS.pop(uid, None)
