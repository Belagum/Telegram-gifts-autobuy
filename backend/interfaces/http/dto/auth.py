from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError

from backend.shared.errors.validation_types import ValidationErrorType


class RegisterRequestDTO(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=12, max_length=128)
    
    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not value:
            raise PydanticCustomError(
                ValidationErrorType.MISSING,
                "Username cannot be empty",
                {}
            )
        
        if not re.match(r'^[a-zA-Z0-9]+$', value):
            raise PydanticCustomError(
                ValidationErrorType.USERNAME_INVALID_CHARS,
                "Username must contain only ASCII letters and digits",
                {"pattern": "^[a-zA-Z0-9]+$"}
            )
        
        if not value[0].isalpha():
            raise PydanticCustomError(
                ValidationErrorType.USERNAME_INVALID_CHARS,
                "Username must start with a letter",
                {"pattern": "^[a-zA-Z][a-zA-Z0-9]*$"}
            )
        
        return value

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if len(value) < 12:
            raise PydanticCustomError(
                ValidationErrorType.PASSWORD_TOO_SHORT,
                "Password must be at least 12 characters long",
                {"min_length": 12}
            )

        if not re.search(r"[A-Z]", value):
            raise PydanticCustomError(
                ValidationErrorType.PASSWORD_NO_UPPERCASE,
                "Password must contain at least one uppercase letter",
                {}
            )

        if not re.search(r"[a-z]", value):
            raise PydanticCustomError(
                ValidationErrorType.PASSWORD_NO_LOWERCASE,
                "Password must contain at least one lowercase letter",
                {}
            )

        if not re.search(r"\d", value):
            raise PydanticCustomError(
                ValidationErrorType.PASSWORD_NO_DIGIT,
                "Password must contain at least one digit",
                {}
            )

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\\/;'`~]", value):
            raise PydanticCustomError(
                ValidationErrorType.PASSWORD_NO_SPECIAL,
                "Password must contain at least one special character",
                {}
            )

        weak_passwords = {
            "123456789012",
            "password1234",
            "qwerty123456",
            "admin1234567",
            "letmein12345",
        }
        if value.lower() in weak_passwords:
            raise PydanticCustomError(
                ValidationErrorType.PASSWORD_WEAK,
                "Password is too weak, please choose a stronger password",
                {}
            )

        return value


class LoginRequestDTO(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=128)  # No strength check on login
    remember_me: bool = False
    
    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not value:
            raise PydanticCustomError(
                ValidationErrorType.MISSING,
                "Username cannot be empty",
                {}
            )
        
        if not re.match(r'^[a-zA-Z0-9]+$', value):
            raise PydanticCustomError(
                ValidationErrorType.USERNAME_INVALID_CHARS,
                "Username must contain only ASCII letters and digits",
                {"pattern": "^[a-zA-Z0-9]+$"}
            )
        
        return value


class AuthSuccessDTO(BaseModel):
    ok: bool = True
