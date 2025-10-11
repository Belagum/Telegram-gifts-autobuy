from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.application.use_cases.users.login_user import LoginUserUseCase
from backend.application.use_cases.users.logout_user import LogoutUserUseCase
from backend.application.use_cases.users.register_user import RegisterUserUseCase
from backend.domain.users.entities import SessionToken, User
from backend.domain.users.exceptions import InvalidCredentialsError, UserAlreadyExistsError
from backend.domain.users.repositories import PasswordHasher, SessionTokenRepository, UserRepository


class InMemoryUserRepository(UserRepository):
    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._seq = 1

    def find_by_username(self, username: str) -> User | None:
        return self._users.get(username)

    def add(self, user: User) -> User:
        new_user = User(
            id=self._seq,
            username=user.username,
            password_hash=user.password_hash,
            created_at=user.created_at,
        )
        self._seq += 1
        self._users[new_user.username] = new_user
        return new_user


class InMemoryTokenRepository(SessionTokenRepository):
    def __init__(self) -> None:
        self._tokens: dict[int, SessionToken] = {}

    def replace_for_user(self, user_id: int) -> SessionToken:
        token = SessionToken(
            user_id=user_id,
            token=f"token-{user_id}",
            expires_at=datetime.now(UTC),
        )
        self._tokens[user_id] = token
        return token

    def revoke(self, token: str) -> None:
        for key, value in list(self._tokens.items()):
            if value.token == token:
                self._tokens.pop(key, None)


class DeterministicHasher(PasswordHasher):
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, hashed: str) -> bool:
        return hashed == f"hashed:{password}"


@pytest.fixture()
def repositories() -> tuple[InMemoryUserRepository, InMemoryTokenRepository]:
    return InMemoryUserRepository(), InMemoryTokenRepository()


def test_register_user_success(
    repositories: tuple[InMemoryUserRepository, InMemoryTokenRepository],
) -> None:
    users, tokens = repositories
    use_case = RegisterUserUseCase(
        users=users, tokens=tokens, password_hasher=DeterministicHasher()
    )

    user, token = use_case.execute("alice", "secret123")

    assert user.username == "alice"
    assert token == "token-1"
    assert users.find_by_username("alice") is not None


def test_register_user_duplicate_raises(
    repositories: tuple[InMemoryUserRepository, InMemoryTokenRepository],
) -> None:
    users, tokens = repositories
    use_case = RegisterUserUseCase(
        users=users, tokens=tokens, password_hasher=DeterministicHasher()
    )
    use_case.execute("alice", "secret123")

    with pytest.raises(UserAlreadyExistsError):
        use_case.execute("alice", "other")


def test_login_user_success(
    repositories: tuple[InMemoryUserRepository, InMemoryTokenRepository],
) -> None:
    users, tokens = repositories
    register = RegisterUserUseCase(
        users=users, tokens=tokens, password_hasher=DeterministicHasher()
    )
    register.execute("alice", "secret123")

    login = LoginUserUseCase(users=users, tokens=tokens, password_hasher=DeterministicHasher())
    assert login.execute("alice", "secret123") == "token-1"


def test_login_user_invalid_credentials(
    repositories: tuple[InMemoryUserRepository, InMemoryTokenRepository],
) -> None:
    users, tokens = repositories
    register = RegisterUserUseCase(
        users=users, tokens=tokens, password_hasher=DeterministicHasher()
    )
    register.execute("alice", "secret123")

    login = LoginUserUseCase(users=users, tokens=tokens, password_hasher=DeterministicHasher())
    with pytest.raises(InvalidCredentialsError):
        login.execute("alice", "wrong")


def test_logout_user_removes_token(
    repositories: tuple[InMemoryUserRepository, InMemoryTokenRepository],
) -> None:
    users, tokens = repositories
    register = RegisterUserUseCase(
        users=users, tokens=tokens, password_hasher=DeterministicHasher()
    )
    _, token = register.execute("alice", "secret123")
    logout = LogoutUserUseCase(tokens=tokens)

    logout.execute(token)

    assert tokens._tokens == {}
