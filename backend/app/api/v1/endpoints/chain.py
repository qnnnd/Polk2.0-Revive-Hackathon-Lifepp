"""
Life++ API — Revive chain config and read-only stats.
Serves real contract addresses and chain health for 13.4 compliance (no fake chain data).
"""
from typing import Any, Optional

from fastapi import APIRouter

from app.api.v1.deps import CurrentUser
from app.core.config import settings
from app.services import chain_service

router = APIRouter(prefix="/chain", tags=["Chain"])


@router.get("/balance")
async def get_my_balance(user: CurrentUser) -> dict[str, Any]:
    """
    Native IVE balance from Revive (13.4: chain-derived). Uses user.wallet_address when set.
    Returns 0 when chain not configured or user has no wallet.
    """
    if not user.wallet_address:
        return {"balance_ive": 0.0, "source": "none"}
    balance = chain_service.balance_of(user.wallet_address)
    if balance is None:
        return {"balance_ive": 0.0, "source": "unavailable"}
    return {"balance_ive": float(balance), "source": "chain"}


@router.get("/config")
async def get_chain_config() -> dict[str, Any]:
    """
    Public chain config for frontend: Revive RPC URL, contract addresses, chain ID.
    Frontend uses this to display real contract address and explorer links (no hardcoded fake data).
    """
    chain_id: Optional[int] = None
    if settings.REVIVE_RPC_URL:
        chain_id = chain_service.get_chain_id()
    return {
        "revive_rpc_url": settings.REVIVE_RPC_URL or "",
        "chain_id": chain_id,
        "task_market_address": settings.TASK_MARKET_ADDRESS or "",
        "agent_registry_address": settings.AGENT_REGISTRY_ADDRESS or "",
        "reputation_address": settings.REPUTATION_ADDRESS or "",
        "configured": settings.revive_configured,
    }


@router.get("/stats")
async def get_chain_stats() -> dict[str, Any]:
    """
    Revive chain stats: connected, block number, total agents on chain.
    Used by dashboard "Testnet Status" so "Agents Registered" comes from chain (13.4).
    """
    connected = chain_service.is_connected()
    block_number: Optional[int] = chain_service.get_block_number() if connected else None
    total_agents_on_chain: Optional[int] = chain_service.total_agents_on_chain() if connected else None
    return {
        "connected": connected,
        "block_number": block_number,
        "total_agents_on_chain": total_agents_on_chain,
        "configured": settings.revive_configured,
    }
