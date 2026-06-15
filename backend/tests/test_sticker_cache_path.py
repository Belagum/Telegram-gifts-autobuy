# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import hashlib

from flask import Flask

import backend.interfaces.http.controllers.gifts_controller as gc


def test_cached_path_uses_hashed_filename_no_traversal():
    app = Flask(__name__)
    app.config["GIFTS_CACHE_DIR"] = "/tmp/gifts_cache_test"
    evil = "../../../../etc/passwd"
    with app.app_context():
        path = gc._cached_path_for(evil)
    # имя файла — это хэш ключа, а не сам ключ → никакого выхода за каталог
    assert path.name == hashlib.sha256(evil.encode()).hexdigest() + ".tgs"
    assert ".." not in path.name and "/" not in path.name and "\\" not in path.name
