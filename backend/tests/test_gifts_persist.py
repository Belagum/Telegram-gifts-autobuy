# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import backend.services.gifts_service as gs


def test_merge_persist_locked_detects_new_and_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(gs, "_GIFTS_DIR", str(tmp_path))
    g1 = {"id": 1, "price": 10}

    merged, added, changed = gs._merge_persist_locked(123, [g1])
    assert changed is True
    assert [x["id"] for x in added] == [1]

    # те же подарки — диск не меняется, новых нет
    _merged, added2, changed2 = gs._merge_persist_locked(123, [g1])
    assert changed2 is False
    assert added2 == []

    # новый подарок — added содержит только его
    g2 = {"id": 2, "price": 20}
    _merged, added3, changed3 = gs._merge_persist_locked(123, [g1, g2])
    assert changed3 is True
    assert [x["id"] for x in added3] == [2]
