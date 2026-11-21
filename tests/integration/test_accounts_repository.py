from __future__ import annotations

import pytest
from sqlalchemy import update

from app.core.utils.time import utcnow
from app.db.models import Account, AccountStatus
from app.db.session import SessionLocal, engine
from app.modules.accounts.repository import AccountsRepository
from tests.integration.statement_capture import capture_task_statements


def _account(
    account_id: str = "acc_refresh",
    *,
    chatgpt_account_id: str = "chatgpt_refresh",
    email: str | None = None,
    workspace_id: str | None = None,
    workspace_label: str | None = None,
) -> Account:
    return Account(
        id=account_id,
        chatgpt_account_id=chatgpt_account_id,
        email=email or f"{account_id}@example.com",
        workspace_id=workspace_id,
        workspace_label=workspace_label,
        plan_type="plus",
        access_token_encrypted=b"access",
        refresh_token_encrypted=b"refresh",
        id_token_encrypted=b"id",
        last_refresh=utcnow(),
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
        limit_warmup_enabled=True,
    )


@pytest.mark.asyncio
async def test_list_accounts_refresh_existing_reloads_identity_map(db_setup):
    del db_setup
    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        await repo.upsert(_account())

    async with SessionLocal() as reader_session:
        reader_repo = AccountsRepository(reader_session)
        loaded = (await reader_repo.list_accounts())[0]
        assert loaded.limit_warmup_enabled is True
        await reader_session.commit()

        async with SessionLocal() as writer_session:
            writer_repo = AccountsRepository(writer_session)
            assert await writer_repo.update_limit_warmup_enabled("acc_refresh", False) is True

        stale = (await reader_repo.list_accounts())[0]
        assert stale is loaded
        assert stale.limit_warmup_enabled is True

        refreshed = (await reader_repo.list_accounts(refresh_existing=True))[0]
        assert refreshed is loaded
        assert refreshed.limit_warmup_enabled is False


@pytest.mark.asyncio
async def test_upsert_account_slot_preserves_emails_sharing_workspace_identity(db_setup):
    del db_setup
    shared_chatgpt_id = "chatgpt_workspace_shared"
    shared_workspace_id = "workspace_shared"
    first = _account(
        "first_slot",
        chatgpt_account_id=shared_chatgpt_id,
        email="first@example.com",
        workspace_id=shared_workspace_id,
    )
    second = _account(
        "second_slot",
        chatgpt_account_id=shared_chatgpt_id,
        email="second@example.com",
        workspace_id=shared_workspace_id,
    )

    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        saved_first = await repo.upsert_account_slot(first, preserve_unknown_workspace_duplicates=False)
        saved_second = await repo.upsert_account_slot(second, preserve_unknown_workspace_duplicates=False)

        assert saved_first.id == "first_slot"
        assert saved_second.id == "second_slot"
        accounts = await repo.list_accounts()

    assert [(account.id, account.email) for account in accounts] == [
        ("first_slot", "first@example.com"),
        ("second_slot", "second@example.com"),
    ]


@pytest.mark.asyncio
async def test_upsert_account_slot_preserves_emails_sharing_workspace_less_identity(db_setup):
    del db_setup
    shared_chatgpt_id = "chatgpt_workspace_less_shared"
    first = _account(
        "workspace_less_first",
        chatgpt_account_id=shared_chatgpt_id,
        email="first@example.com",
    )
    second = _account(
        "workspace_less_second",
        chatgpt_account_id=shared_chatgpt_id,
        email="second@example.com",
    )

    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        saved_first = await repo.upsert_account_slot(first, preserve_unknown_workspace_duplicates=False)
        saved_second = await repo.upsert_account_slot(second, preserve_unknown_workspace_duplicates=False)

        assert saved_first.id == "workspace_less_first"
        assert saved_second.id == "workspace_less_second"
        accounts = await repo.list_accounts()

    assert [(account.id, account.email) for account in accounts] == [
        ("workspace_less_first", "first@example.com"),
        ("workspace_less_second", "second@example.com"),
    ]


@pytest.mark.asyncio
async def test_upsert_account_slot_preserves_same_chatgpt_id_across_workspace_ids(db_setup):
    del db_setup
    first = _account(
        "mavos_primary",
        chatgpt_account_id="chatgpt_mavos_shared",
        email="operator@example.com",
        workspace_id="ws_mavos_primary",
    )
    second = _account(
        "mavos_secondary",
        chatgpt_account_id="chatgpt_mavos_shared",
        email="operator@example.com",
        workspace_id="ws_mavos_secondary",
    )

    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        saved_first = await repo.upsert_account_slot(first, preserve_unknown_workspace_duplicates=False)
        saved_second = await repo.upsert_account_slot(second, preserve_unknown_workspace_duplicates=False)
        accounts = await repo.list_accounts()

    assert saved_first.id == "mavos_primary"
    assert saved_second.id == "mavos_secondary"
    assert [(account.id, account.workspace_id) for account in accounts] == [
        ("mavos_primary", "ws_mavos_primary"),
        ("mavos_secondary", "ws_mavos_secondary"),
    ]


@pytest.mark.asyncio
async def test_upsert_account_slot_adds_third_workspace_slot_for_same_email(db_setup):
    del db_setup
    first = _account(
        "mavos_primary",
        chatgpt_account_id="chatgpt_mavos_primary",
        email="operator@example.com",
        workspace_id="ws_mavos_primary",
    )
    second = _account(
        "mavos_secondary",
        chatgpt_account_id="chatgpt_mavos_secondary",
        email="operator@example.com",
        workspace_id="ws_mavos_secondary",
    )
    third = _account(
        "mavos_tertiary",
        chatgpt_account_id="chatgpt_mavos_tertiary",
        email="operator@example.com",
        workspace_id="ws_mavos_tertiary",
    )

    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        saved_first = await repo.upsert_account_slot(first, preserve_unknown_workspace_duplicates=False)
        saved_second = await repo.upsert_account_slot(second, preserve_unknown_workspace_duplicates=False)
        saved_third = await repo.upsert_account_slot(third, preserve_unknown_workspace_duplicates=False)
        accounts = await repo.list_accounts()

    assert saved_first.id == "mavos_primary"
    assert saved_second.id == "mavos_secondary"
    assert saved_third.id == "mavos_tertiary"
    assert [(account.id, account.workspace_id) for account in accounts] == [
        ("mavos_primary", "ws_mavos_primary"),
        ("mavos_secondary", "ws_mavos_secondary"),
        ("mavos_tertiary", "ws_mavos_tertiary"),
    ]


@pytest.mark.asyncio
async def test_upsert_account_slot_preserves_same_chatgpt_id_across_workspace_labels(db_setup):
    del db_setup
    first = _account(
        "mavos_workspace",
        chatgpt_account_id="chatgpt_mavos_shared_label",
        email="operator@example.com",
        workspace_label="Mavos",
    )
    second = _account(
        "triton_workspace",
        chatgpt_account_id="chatgpt_mavos_shared_label",
        email="operator@example.com",
        workspace_label="Triton",
    )

    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        saved_first = await repo.upsert_account_slot(first, preserve_unknown_workspace_duplicates=False)
        saved_second = await repo.upsert_account_slot(second, preserve_unknown_workspace_duplicates=False)
        accounts = await repo.list_accounts()

    assert saved_first.id == "mavos_workspace"
    assert saved_second.id == "triton_workspace"
    assert [(account.id, account.workspace_label) for account in accounts] == [
        ("mavos_workspace", "Mavos"),
        ("triton_workspace", "Triton"),
    ]


@pytest.mark.asyncio
async def test_upsert_account_slot_adds_third_label_only_workspace_for_same_email(db_setup):
    del db_setup
    first = _account(
        "mavos_workspace",
        chatgpt_account_id="chatgpt_label_slots",
        email="operator@example.com",
        workspace_label="Mavos",
    )
    second = _account(
        "triton_workspace",
        chatgpt_account_id="chatgpt_label_slots",
        email="operator@example.com",
        workspace_label="Triton",
    )
    third = _account(
        "atlas_workspace",
        chatgpt_account_id="chatgpt_label_slots",
        email="operator@example.com",
        workspace_label="Atlas",
    )

    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        saved_first = await repo.upsert_account_slot(first, preserve_unknown_workspace_duplicates=False)
        saved_second = await repo.upsert_account_slot(second, preserve_unknown_workspace_duplicates=False)
        saved_third = await repo.upsert_account_slot(third, preserve_unknown_workspace_duplicates=False)
        accounts = await repo.list_accounts()

    assert saved_first.id == "mavos_workspace"
    assert saved_second.id == "triton_workspace"
    assert saved_third.id == "atlas_workspace"
    assert [(account.id, account.workspace_label) for account in accounts] == [
        ("mavos_workspace", "Mavos"),
        ("triton_workspace", "Triton"),
        ("atlas_workspace", "Atlas"),
    ]


async def _seed_id_query_accounts() -> None:
    rows = [
        ("acc_active", AccountStatus.ACTIVE, True, "plus", False),
        ("acc_rate_limited", AccountStatus.RATE_LIMITED, True, "plus", False),
        ("acc_quota", AccountStatus.QUOTA_EXCEEDED, True, "plus", False),
        ("acc_paused", AccountStatus.PAUSED, True, "plus", False),
        ("acc_reauth", AccountStatus.REAUTH_REQUIRED, True, "plus", False),
        ("acc_deactivated", AccountStatus.DEACTIVATED, True, "plus", False),
        ("acc_deleted", AccountStatus.ACTIVE, True, "plus", True),
        ("acc_opt_out", AccountStatus.ACTIVE, False, "plus", False),
        ("acc_free", AccountStatus.ACTIVE, True, "free", False),
    ]
    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        for account_id, status, warmup_enabled, plan_type, deleted in rows:
            account = _account(account_id, chatgpt_account_id=f"chatgpt_{account_id}")
            account.status = status
            account.limit_warmup_enabled = warmup_enabled
            account.plan_type = plan_type
            await repo.upsert(account)
            if deleted:
                await session.execute(
                    update(Account).where(Account.id == account_id).values(delete_requested_at=utcnow())
                )
        await session.commit()


def _assert_id_only_select(statements: list[str]) -> None:
    selects = [statement for statement in statements if statement.startswith("select")]
    assert len(selects) == 1
    projection = selects[0].split(" from ", 1)[0]
    assert projection == "select accounts.id"


@pytest.mark.asyncio
async def test_list_account_ids_selects_only_ids_and_applies_rotation_filters(db_setup):
    del db_setup
    await _seed_id_query_accounts()

    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        async with capture_task_statements(engine) as statements:
            ids = await repo.list_account_ids(
                excluded_statuses=(AccountStatus.PAUSED, AccountStatus.REAUTH_REQUIRED, AccountStatus.DEACTIVATED)
            )
        all_ids = await repo.list_account_ids()

    _assert_id_only_select(statements)
    assert sorted(ids) == [
        "acc_active",
        "acc_free",
        "acc_opt_out",
        "acc_quota",
        "acc_rate_limited",
    ]
    assert "acc_deleted" not in all_ids
    assert {"acc_paused", "acc_reauth", "acc_deactivated"} <= set(all_ids)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("selected_id", "selected_status", "selected_plan_type", "selected_included"),
    [
        ("acc_rate_limited", AccountStatus.RATE_LIMITED, "plus", True),
        ("acc_rate_limited", AccountStatus.ACTIVE, "plus", False),
        ("acc_rate_limited", AccountStatus.RATE_LIMITED, "free", False),
        ("acc_opt_out", AccountStatus.ACTIVE, "plus", False),
        ("acc_deleted", AccountStatus.ACTIVE, "plus", False),
        ("acc_rate_limited", None, None, False),
        # An active, opted-in selected row must enter only through the
        # snapshot-checked branch, never through the peer branch.
        ("acc_active", AccountStatus.ACTIVE, "plus", True),
        ("acc_active", AccountStatus.ACTIVE, "free", False),
        ("acc_active", AccountStatus.RATE_LIMITED, "plus", False),
        ("acc_active", None, None, False),
    ],
)
async def test_list_limit_warmup_stagger_account_ids_checks_selected_snapshot(
    db_setup,
    selected_id: str,
    selected_status: AccountStatus | None,
    selected_plan_type: str | None,
    selected_included: bool,
):
    del db_setup
    await _seed_id_query_accounts()

    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        async with capture_task_statements(engine) as statements:
            ids = await repo.list_limit_warmup_stagger_account_ids(
                selected_account_id=selected_id,
                selected_status=selected_status,
                selected_plan_type=selected_plan_type,
            )

    _assert_id_only_select(statements)
    peers = {"acc_active", "acc_free"} - {selected_id}
    expected = peers | ({selected_id} if selected_included else set())
    assert set(ids) == expected
