from collections.abc import Iterable, Sequence

import pytest
from backend.application.use_cases.autobuy import AutobuyInput, AutobuyUseCase
from backend.domain import AccountSnapshot, ChannelFilter


class FakeAccountRepository:
    def __init__(self, accounts: Sequence[AccountSnapshot]):
        self._accounts = list(accounts)

    def list_for_user(self, user_id: int) -> Sequence[AccountSnapshot]:
        return list(self._accounts)


class FakeChannelRepository:
    def __init__(self, channels: Sequence[ChannelFilter]):
        self._channels = list(channels)

    def list_for_user(self, user_id: int) -> Sequence[ChannelFilter]:
        return list(self._channels)


class FakeSettingsRepository:
    def __init__(self, token: str | None):
        self._token = token

    def get_bot_token(self, user_id: int) -> str | None:
        return self._token


class FakeTelegramPort:
    def __init__(self, balances: dict[int, int]):
        self._balances = balances
        self.sent: list[tuple[int, int]] = []

    async def fetch_balance(self, account: AccountSnapshot) -> int:
        return self._balances.get(account.id, 0)

    async def send_gift(self, operation, account: AccountSnapshot) -> None:
        self.sent.append((operation.gift_id, operation.account_id))

    async def resolve_self_ids(self, accounts: Iterable[AccountSnapshot]) -> list[int]:
        return [42]


class FakeNotificationPort:
    def __init__(self) -> None:
        self.sent_payloads: list[tuple[str, list[int], list[str]]] = []

    async def send_reports(
        self, token: str, chat_ids: Sequence[int], messages: Sequence[str]
    ) -> None:
        self.sent_payloads.append((token, list(chat_ids), list(messages)))


@pytest.mark.asyncio
async def test_autobuy_use_case_executes_plan() -> None:
    accounts = [
        AccountSnapshot(
            id=1,
            user_id=1,
            session_path="/tmp/a",
            api_id=1,
            api_hash="hash",
            is_premium=False,
            balance=0,
        ),
    ]
    channels = [
        ChannelFilter(
            id=1,
            user_id=1,
            channel_id=-100,
            price_min=0,
            price_max=100,
            supply_min=0,
            supply_max=10,
        )
    ]
    account_repo = FakeAccountRepository(accounts)
    channel_repo = FakeChannelRepository(channels)
    settings_repo = FakeSettingsRepository("token")
    telegram_port = FakeTelegramPort({1: 50})
    notify_port = FakeNotificationPort()

    use_case = AutobuyUseCase(
        accounts=account_repo,
        channels=channel_repo,
        telegram=telegram_port,
        notifications=notify_port,
        settings=settings_repo,
    )

    gifts: list[dict[str, object]] = [
        {
            "id": 10,
            "price": 25,
            "is_limited": True,
            "total_amount": 2,
            "available_amount": 2,
            "limited_per_user": False,
        }
    ]

    output = await use_case.execute(AutobuyInput(user_id=1, gifts=gifts))

    assert len(output.purchased) == 2
    assert telegram_port.sent == [(10, 1), (10, 1)]
    assert notify_port.sent_payloads  # report was sent


@pytest.mark.asyncio
async def test_autobuy_use_case_skips_invalid_gifts() -> None:
    account_repo = FakeAccountRepository(
        [
            AccountSnapshot(
                id=1,
                user_id=1,
                session_path="/tmp/a",
                api_id=1,
                api_hash="hash",
                is_premium=False,
                balance=0,
            ),
        ]
    )
    channel_repo = FakeChannelRepository(
        [
            ChannelFilter(
                id=1,
                user_id=1,
                channel_id=-200,
                price_min=0,
                price_max=100,
                supply_min=0,
                supply_max=10,
            )
        ]
    )
    settings_repo = FakeSettingsRepository(None)
    telegram_port = FakeTelegramPort({1: 10})
    notify_port = FakeNotificationPort()

    use_case = AutobuyUseCase(
        accounts=account_repo,
        channels=channel_repo,
        telegram=telegram_port,
        notifications=notify_port,
        settings=settings_repo,
    )

    gifts: list[dict[str, object]] = [
        {
            "id": 10,
            "price": 0,
            "is_limited": True,
            "total_amount": 1,
            "available_amount": 1,
        },
        {
            "id": 11,
            "price": 10,
            "is_limited": False,
            "total_amount": 5,
            "available_amount": 1,
        },
    ]

    output = await use_case.execute(AutobuyInput(user_id=1, gifts=gifts))

    assert output.purchased == []
    assert any(skip.get("reason") == "invalid/price" for skip in output.stats["global_skips"])
    assert any(skip.get("reason") == "unlimited" for skip in output.stats["global_skips"])
