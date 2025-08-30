# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

import os, threading
from typing import Dict
_LOCKS: Dict[str, threading.RLock] = {}
_GUARD = threading.Lock()

def session_lock_for(session_path: str) -> threading.RLock:
    key = os.path.abspath(session_path or "")
    with _GUARD: lk = _LOCKS.get(key)
    if lk is None: lk = threading.RLock()
    _LOCKS[key] = lk
    return lk