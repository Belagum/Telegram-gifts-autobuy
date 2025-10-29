# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from datetime import UTC, datetime

from backend.infrastructure.db.models import Account, ApiProfile
from backend.infrastructure.telegram_auth.exceptions import RepositoryError
from backend.infrastructure.telegram_auth.models.dto import (
    AccountData,
    ApiCredentials,
)
from backend.shared.logging import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class SQLAlchemyAccountRepository:
    def __init__(self, db_session: Session) -> None:
        self._db = db_session
        logger.debug("SQLAlchemyAccountRepository: initialized")

    def get_api_credentials(
        self,
        user_id: int,
        api_profile_id: int
    ) -> ApiCredentials | None:
        api_profile = self._db.get(ApiProfile, api_profile_id)
        
        if not api_profile or api_profile.user_id != user_id:
            logger.warning(
                f"SQLAlchemyAccountRepository: api profile not found or mismatch "
                f"user_id={user_id} api_profile_id={api_profile_id}"
            )
            return None
        
        credentials = ApiCredentials(
            api_id=api_profile.api_id,
            api_hash=api_profile.api_hash
        )
        
        logger.debug(
            f"SQLAlchemyAccountRepository: credentials retrieved "
            f"api_id={credentials.api_id}"
        )
        
        return credentials

    def save_account(
        self,
        user_id: int,
        api_profile_id: int,
        phone: str,
        session_path: str,
        account_data: AccountData
    ) -> None:
        telegram_id = account_data.telegram_id
        
        logger.info(
            f"SQLAlchemyAccountRepository: saving account "
            f"user_id={user_id} phone={phone} tg_id={telegram_id}"
        )
        
        try:
            account = self._find_existing_account(user_id, phone, telegram_id)
            
            if not account:
                account = self._create_new_account(
                    user_id,
                    api_profile_id,
                    phone,
                    session_path,
                    telegram_id
                )
            
            self._update_account_data(account, account_data, session_path)
            
            self._commit_account(account, user_id, phone, telegram_id)
            
        except Exception as e:
            logger.exception(
                f"SQLAlchemyAccountRepository: failed to save account "
                f"user_id={user_id} phone={phone}"
            )
            raise RepositoryError(
                f"Failed to save account: {e}",
                error_code="save_account_failed"
            ) from e

    def _find_existing_account(
        self,
        user_id: int,
        phone: str,
        telegram_id: int | None
    ) -> Account | None:
        account = (
            self._db.query(Account)
            .filter(Account.user_id == user_id, Account.phone == phone)
            .first()
        )
        
        if not account and telegram_id:
            account = self._db.get(Account, telegram_id)
        
        return account

    def _create_new_account(
        self,
        user_id: int,
        api_profile_id: int,
        phone: str,
        session_path: str,
        telegram_id: int | None
    ) -> Account:
        if telegram_id:
            logger.debug(
                f"SQLAlchemyAccountRepository: creating account with tg_id "
                f"tg_id={telegram_id} user_id={user_id}"
            )
            account = Account(
                id=telegram_id,
                user_id=user_id,
                api_profile_id=api_profile_id,
                phone=phone,
                session_path=session_path
            )
        else:
            logger.debug(
                f"SQLAlchemyAccountRepository: creating account without tg_id "
                f"user_id={user_id} phone={phone}"
            )
            account = Account(
                user_id=user_id,
                api_profile_id=api_profile_id,
                phone=phone,
                session_path=session_path
            )
        
        self._db.add(account)
        return account

    def _update_account_data(
        self,
        account: Account,
        account_data: AccountData,
        session_path: str
    ) -> None:
        account.username = account_data.username
        account.first_name = account_data.first_name
        account.stars_amount = account_data.stars_amount
        account.is_premium = account_data.is_premium
        account.premium_until = account_data.premium_until
        account.session_path = session_path
        account.last_checked_at = datetime.now(UTC)

    def _commit_account(
        self,
        account: Account,
        user_id: int,
        phone: str,
        telegram_id: int | None
    ) -> None:
        try:
            self._db.commit()
            logger.info(
                f"SQLAlchemyAccountRepository: account saved "
                f"user_id={user_id} phone={phone} tg_id={telegram_id}"
            )
        except IntegrityError:
            logger.warning(
                f"SQLAlchemyAccountRepository: integrity error, retrying "
                f"user_id={user_id} phone={phone}"
            )
            self._db.rollback()
            
            if telegram_id:
                self._retry_update_existing_account(telegram_id, account)
            else:
                raise

    def _retry_update_existing_account(
        self,
        telegram_id: int,
        source_account: Account
    ) -> None:
        existing_account = self._db.get(Account, telegram_id)
        
        if not existing_account:
            raise RepositoryError(
                f"Account with tg_id={telegram_id} not found after IntegrityError",
                error_code="account_not_found_after_integrity_error"
            )
        
        logger.debug(
            f"SQLAlchemyAccountRepository: retry update existing account "
            f"tg_id={telegram_id}"
        )
        
        existing_account.user_id = source_account.user_id
        existing_account.api_profile_id = source_account.api_profile_id
        existing_account.phone = source_account.phone
        existing_account.session_path = source_account.session_path
        existing_account.username = source_account.username
        existing_account.first_name = source_account.first_name
        existing_account.stars_amount = source_account.stars_amount
        existing_account.is_premium = source_account.is_premium
        existing_account.premium_until = source_account.premium_until
        existing_account.last_checked_at = source_account.last_checked_at
        
        self._db.commit()
        
        logger.info(
            f"SQLAlchemyAccountRepository: account updated after retry "
            f"tg_id={telegram_id}"
        )

