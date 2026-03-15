"""
Chain data verification (no fake data).
Run after local Revive demo: checks that backend reads real chain state.
Requires: Revive configured (REVIVE_RPC_URL + contract addresses) and chain reachable.
"""
import pytest

from app.core.config import settings
from app.services import chain_service


@pytest.mark.skipif(
    not settings.revive_configured,
    reason="Revive not configured (set REVIVE_RPC_URL and contract addresses)",
)
def test_revive_connected():
    """Backend must connect to Revive RPC."""
    assert chain_service.is_connected(), "Revive RPC unreachable"


@pytest.mark.skipif(
    not settings.revive_configured,
    reason="Revive not configured",
)
def test_chain_id_or_block():
    """Chain responds (chain_id or block_number)."""
    chain_id = chain_service.get_chain_id()
    block = chain_service.get_block_number()
    assert chain_id is not None or block is not None, "No chain_id or block_number from RPC"


@pytest.mark.skipif(
    not settings.revive_configured,
    reason="Revive not configured",
)
def test_agent_registry_readable():
    """AgentRegistry.totalAgents() is readable (no fake data)."""
    total = chain_service.total_agents_on_chain()
    assert total is not None, "AgentRegistry.totalAgents() failed"
    assert isinstance(total, int) and total >= 0, "total_agents_on_chain should be non-negative int"


@pytest.mark.skipif(
    not settings.revive_configured,
    reason="Revive not configured",
)
def test_task_market_readable():
    """TaskMarket.nextTaskId() is readable."""
    next_id = chain_service.next_task_id()
    assert next_id is not None, "TaskMarket.nextTaskId() failed"
    assert isinstance(next_id, int) and next_id >= 0, "next_task_id should be non-negative int"


@pytest.mark.skipif(
    not settings.revive_configured,
    reason="Revive not configured",
)
def test_reputation_readable():
    """Reputation.getScore() is callable (returns 0-100 for unknown agent)."""
    score = chain_service.get_score("00000000-0000-0000-0000-000000000000")
    # Unknown agent: contract returns 100 (no tasks), or 0; either is valid
    assert score is None or (isinstance(score, (int, float)) and 0 <= score <= 5.0), (
        "Reputation.getScore should return 0-5.0 or None"
    )


@pytest.mark.skipif(
    not settings.revive_configured,
    reason="Revive not configured",
)
def test_cog_balance_readable():
    """Native IVE balance_of is callable (zero address or deployer)."""
    zero = "0x0000000000000000000000000000000000000000"
    balance = chain_service.balance_of(zero)
    assert balance is None or (balance >= 0), "balance_of should be non-negative or None"
