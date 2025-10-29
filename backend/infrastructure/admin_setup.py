# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import sys

from backend.infrastructure.db.models import User
from backend.infrastructure.db.session import SessionLocal
from backend.shared.config import load_config
from backend.shared.logging import logger


class AdminSetupError(Exception):
    pass


class AdminSetup:
    @staticmethod
    def setup_admin_user() -> None:
        config = load_config()
        
        if not config.admin_username:
            logger.info("admin_setup: No ADMIN_USERNAME configured, skipping admin setup")
            return
        
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == config.admin_username).first()
            
            if not user:
                error_msg = (
                    f"ADMIN_USERNAME '{config.admin_username}' not found in database. "
                    f"Please create this user first or update ADMIN_USERNAME."
                )
                logger.error(f"admin_setup: {error_msg}")
                print(f"\n❌ ADMIN SETUP ERROR: {error_msg}\n", file=sys.stderr)
                sys.exit(1)
            
            if not user.is_admin:
                user.is_admin = True
                db.commit()
                logger.info(f"admin_setup: Granted admin privileges to user '{config.admin_username}'")
            else:
                logger.info(f"admin_setup: User '{config.admin_username}' already has admin privileges")
                
        except Exception as e:
            db.rollback()
            logger.error(f"admin_setup: Failed to setup admin user: {e}")
            raise AdminSetupError(f"Failed to setup admin user: {e}") from e
        finally:
            db.close()


def setup_admin_user() -> None:
    AdminSetup.setup_admin_user()


__all__ = [
    "AdminSetup",
    "AdminSetupError",
    "setup_admin_user",
]

