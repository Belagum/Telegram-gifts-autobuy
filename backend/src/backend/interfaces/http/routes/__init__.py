# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""HTTP blueprints exposed by the web application."""

from .account import bp_acc
from .channels import bp_channels
from .gifts import bp_gifts
from .misc import bp_misc
from .settings import bp_settings

__all__ = [
    "bp_acc",
    "bp_channels",
    "bp_gifts",
    "bp_misc",
    "bp_settings",
]
