from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequestDTO(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class LoginRequestDTO(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class AuthSuccessDTO(BaseModel):
    ok: bool = True
