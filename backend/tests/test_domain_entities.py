import pytest
from backend.domain import (
    AccountSnapshot,
    ChannelFilter,
    GiftCandidate,
    InvariantViolation,
)


def test_channel_filter_validates_ranges() -> None:
    filt = ChannelFilter(
        id=1,
        user_id=1,
        channel_id=-100,
        price_min=10,
        price_max=100,
        supply_min=1,
        supply_max=10,
    )
    gift = GiftCandidate(
        gift_id=1,
        price=50,
        total_supply=5,
        available_amount=5,
        per_user_cap=1,
        require_premium=False,
    )
    assert filt.matches(gift) is True


def test_channel_filter_rejects_invalid_ranges() -> None:
    with pytest.raises(InvariantViolation):
        ChannelFilter(
            id=1,
            user_id=1,
            channel_id=-100,
            price_min=100,
            price_max=10,
            supply_min=None,
            supply_max=None,
        )


def test_account_snapshot_debit_updates_balance() -> None:
    account = AccountSnapshot(
        id=1,
        user_id=1,
        session_path="/tmp",
        api_id=1,
        api_hash="hash",
        is_premium=False,
        balance=100,
    )
    account.debit(40)
    assert account.balance == 60
    with pytest.raises(InvariantViolation):
        account.debit(1000)


def test_gift_candidate_priority_key() -> None:
    gift_low = GiftCandidate(
        gift_id=1,
        price=10,
        total_supply=1,
        available_amount=1,
        per_user_cap=1,
        require_premium=False,
    )
    gift_high = GiftCandidate(
        gift_id=2,
        price=20,
        total_supply=5,
        available_amount=5,
        per_user_cap=1,
        require_premium=False,
    )
    assert gift_low.priority_key() < gift_high.priority_key()
