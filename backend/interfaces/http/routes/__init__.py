# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from backend.interfaces.http.controllers.accounts_controller import AccountsController
from backend.interfaces.http.controllers.channels_controller import ChannelsController
from backend.interfaces.http.controllers.gifts_controller import GiftsController
from backend.interfaces.http.controllers.misc_controller import MiscController
from backend.interfaces.http.controllers.settings_controller import SettingsController

_accounts_controller = AccountsController()
_channels_controller = ChannelsController()
_gifts_controller = GiftsController()
_misc_controller = MiscController()
_settings_controller = SettingsController()

bp_acc = _accounts_controller.as_blueprint()
bp_channels = _channels_controller.as_blueprint()
bp_gifts = _gifts_controller.as_blueprint()
bp_misc = _misc_controller.as_blueprint()
bp_settings = _settings_controller.as_blueprint()

__all__ = [
    "bp_acc",
    "bp_channels",
    "bp_gifts",
    "bp_misc",
    "bp_settings",
]
