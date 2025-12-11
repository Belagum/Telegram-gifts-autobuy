# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from typing import Any

from pyrogram import Client
from pyrogram.errors import RPCError, SessionPasswordNeeded

from backend.infrastructure.telegram_auth.exceptions import LoginError
from backend.infrastructure.telegram_auth.interfaces.event_loop import \
    IEventLoop
from backend.infrastructure.telegram_auth.models.dto import (AccountData,
                                                             ApiCredentials)
from backend.infrastructure.telegram_auth.telegram_error_mapper import \
    map_telegram_error
from backend.services.accounts_service import fetch_profile_and_stars
from backend.shared.logging import logger


class PyrogramClientWrapper:
    def __init__(
        self, session_path: str, credentials: ApiCredentials, event_loop: IEventLoop
    ) -> None:
        self._session_path = session_path
        self._credentials = credentials
        self._event_loop = event_loop
        self._client: Client | None = None

        logger.debug(
            f"PyrogramClientWrapper: initialized "
            f"session={session_path} api_id={credentials.api_id}"
        )

    async def _connect_and_send_code(self, phone: str) -> tuple[Client, str]:
        logger.debug(f"PyrogramClientWrapper: connecting session={self._session_path}")

        client = Client(
            self._session_path,
            api_id=self._credentials.api_id,
            api_hash=self._credentials.api_hash,
            no_updates=True,
        )

        try:
            await client.connect()
            logger.debug(
                f"PyrogramClientWrapper: connected session={self._session_path}"
            )

            await client.initialize()
            logger.debug(
                f"PyrogramClientWrapper: initialized session={self._session_path}"
            )

            sent = await client.send_code(phone)
            phone_code_hash = getattr(sent, "phone_code_hash", None)

            if not isinstance(phone_code_hash, str):
                raise LoginError(
                    "Missing phone_code_hash in send_code response",
                    error_code="send_code_failed",
                )

            logger.info(
                f"PyrogramClientWrapper: code sent "
                f"session={self._session_path} phone={phone} hash={phone_code_hash}"
            )

            return client, phone_code_hash
        except RPCError as e:
            error_code, context = map_telegram_error(e)
            logger.warning(
                f"PyrogramClientWrapper: RPC error during connect/send_code "
                f"type={e.__class__.__name__} code={error_code} detail={str(e)[:200]}"
            )
            raise LoginError(
                f"Telegram RPC error: {e}", error_code=error_code, context=context
            ) from e

    def connect_and_send_code(self, phone: str) -> tuple[Any, str]:
        client, code_hash = self._event_loop.run(self._connect_and_send_code(phone))
        self._client = client
        return client, code_hash

    async def _sign_in(
        self, client: Any, phone: str, phone_code_hash: str, phone_code: str
    ) -> bool:
        try:
            await client.sign_in(
                phone_number=phone,
                phone_code_hash=phone_code_hash,
                phone_code=phone_code,
            )
            return True
        except SessionPasswordNeeded:
            raise
        except RPCError as e:
            error_code, context = map_telegram_error(e)
            logger.warning(
                f"PyrogramClientWrapper: RPC error during sign_in "
                f"type={e.__class__.__name__} code={error_code} detail={str(e)[:200]}"
            )
            raise LoginError(
                f"Telegram RPC error: {e}", error_code=error_code, context=context
            ) from e

    def sign_in_with_code(
        self, client: Any, phone: str, phone_code_hash: str, code: str
    ) -> bool:
        try:
            self._event_loop.run(self._sign_in(client, phone, phone_code_hash, code))
            logger.debug(f"PyrogramClientWrapper: sign_in success phone={phone}")
            return True
        except SessionPasswordNeeded:
            logger.info(f"PyrogramClientWrapper: 2FA required phone={phone}")
            return False

    async def _check_password(self, client: Any, password: str) -> None:
        try:
            await client.check_password(password)
        except RPCError as e:
            error_code, context = map_telegram_error(e)
            logger.warning(
                f"PyrogramClientWrapper: RPC error during check_password "
                f"type={e.__class__.__name__} code={error_code} detail={str(e)[:200]}"
            )
            raise LoginError(
                f"Telegram RPC error: {e}", error_code=error_code, context=context
            ) from e

    def confirm_2fa(self, client: Any, password: str) -> None:
        self._event_loop.run(self._check_password(client, password))
        logger.debug("PyrogramClientWrapper: 2FA password confirmed")

    def fetch_account_data(self) -> AccountData:
        try:
            me, stars, premium, until = self._event_loop.run(
                fetch_profile_and_stars(
                    self._session_path,
                    self._credentials.api_id,
                    self._credentials.api_hash,
                )
            )

            telegram_id = int(getattr(me, "id", 0)) or None

            account_data = AccountData(
                telegram_id=telegram_id,
                username=getattr(me, "username", None),
                first_name=getattr(me, "first_name", None),
                stars_amount=int(stars),
                is_premium=bool(premium),
                premium_until=until,
            )

            logger.info(
                f"PyrogramClientWrapper: account data fetched "
                f"tg_id={telegram_id} stars={stars}"
            )

            return account_data
        except Exception as e:
            logger.exception("PyrogramClientWrapper: failed to fetch account data")
            raise LoginError(
                f"Failed to fetch account data: {e}",
                error_code="fetch_account_data_failed",
            ) from e

    async def _disconnect(self, client: Any) -> None:
        await client.disconnect()

    def disconnect(self, client: Any) -> None:
        try:
            self._event_loop.run(self._disconnect(client))
            logger.debug("PyrogramClientWrapper: client disconnected")
        except Exception:
            logger.exception("PyrogramClientWrapper: failed to disconnect client")
