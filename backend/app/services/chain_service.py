"""
Life++ — Revive testnet chain service (read-only + optional writes).
Uses web3.py to call COGToken, AgentRegistry, TaskMarket, Reputation contracts.
All chain-derived data for 13.4 compliance must go through this service.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from web3 import Web3
from web3.exceptions import ContractLogicError

from app.core.config import settings

# COG has 18 decimals (wei)
COG_DECIMALS = 18


def _w3() -> Optional[Web3]:
    """
    Web3 provider factory.

    In development:
    - Default to local Revive node at http://127.0.0.1:8545 when REVIVE_RPC_URL is unset.
    - Never fall back to a remote Revive RPC; that is blocked at config level.
    """
    url: Optional[str] = settings.REVIVE_RPC_URL
    if settings.is_development and (not url or not url.strip()):
        url = "http://127.0.0.1:8545"
    if not url:
        return None
    return Web3(Web3.HTTPProvider(url))


def is_connected() -> bool:
    if not _w3():
        return False
    try:
        return _w3().is_connected()
    except Exception:
        return False


def get_chain_id() -> Optional[int]:
    w3 = _w3()
    if not w3:
        return None
    try:
        return w3.eth.chain_id
    except Exception:
        return None


def get_block_number() -> Optional[int]:
    w3 = _w3()
    if not w3:
        return None
    try:
        return w3.eth.block_number
    except Exception:
        return None


# Minimal ABIs (view + write)
ABI_COG = [
    {"inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "name": "approve", "outputs": [{"type": "bool"}], "stateMutability": "nonpayable", "type": "function"},
]
ABI_AGENT_REGISTRY = [
    {"inputs": [{"name": "agentId", "type": "string"}], "name": "getAgent", "outputs": [
        {"name": "owner", "type": "address"},
        {"name": "agentId", "type": "string"},
        {"name": "name", "type": "string"},
        {"name": "metadataURI", "type": "string"},
        {"name": "registeredAt", "type": "uint256"},
        {"name": "active", "type": "bool"},
    ], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "totalAgents", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [
        {"name": "agentId", "type": "string"},
        {"name": "name", "type": "string"},
        {"name": "metadataURI", "type": "string"},
    ], "name": "register", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
]
# TaskMarket.TaskStatus: Open=0, Accepted=1, Completed=2, Cancelled=3
ABI_TASK_MARKET = [
    {"inputs": [{"name": "taskId", "type": "uint256"}], "name": "getTask", "outputs": [
        {"name": "id", "type": "uint256"},
        {"name": "poster", "type": "address"},
        {"name": "posterAgentId", "type": "string"},
        {"name": "title", "type": "string"},
        {"name": "rewardAmount", "type": "uint256"},
        {"name": "status", "type": "uint8"},
        {"name": "acceptor", "type": "address"},
        {"name": "acceptorAgentId", "type": "string"},
        {"name": "createdAt", "type": "uint256"},
        {"name": "completedAt", "type": "uint256"},
    ], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "nextTaskId", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "posterAgentId", "type": "string"}, {"name": "title", "type": "string"}, {"name": "rewardAmount", "type": "uint256"}], "name": "createTask", "outputs": [{"type": "uint256"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "taskId", "type": "uint256"}, {"name": "acceptorAgentId", "type": "string"}], "name": "acceptTask", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "taskId", "type": "uint256"}], "name": "completeTask", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
]
ABI_REPUTATION = [
    {"inputs": [{"name": "agentId", "type": "string"}], "name": "getReputation", "outputs": [
        {"name": "tasksCompleted", "type": "uint256"},
        {"name": "tasksFailed", "type": "uint256"},
        {"name": "totalCogEarned", "type": "uint256"},
        {"name": "endorsements", "type": "uint256"},
        {"name": "lastUpdated", "type": "uint256"},
    ], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "agentId", "type": "string"}], "name": "getScore", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "agentId", "type": "string"}, {"name": "cogEarned", "type": "uint256"}], "name": "recordTaskComplete", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
]


def balance_of(address: str) -> Optional[Decimal]:
    """COGToken.balanceOf(account) in human COG (not wei)."""
    if not settings.revive_configured or not settings.COG_TOKEN_ADDRESS:
        return None
    w3 = _w3()
    if not w3 or not address:
        return None
    try:
        contract = w3.eth.contract(address=Web3.to_checksum_address(settings.COG_TOKEN_ADDRESS), abi=ABI_COG)
        wei = contract.functions.balanceOf(Web3.to_checksum_address(address)).call()
        return Decimal(wei) / (10**COG_DECIMALS)
    except Exception:
        return None


def get_agent(agent_id: str) -> Optional[dict[str, Any]]:
    """AgentRegistry.getAgent(agentId). Returns dict with owner, agentId, name, metadataURI, registeredAt, active."""
    if not settings.revive_configured or not settings.AGENT_REGISTRY_ADDRESS:
        return None
    w3 = _w3()
    if not w3:
        return None
    try:
        contract = w3.eth.contract(address=Web3.to_checksum_address(settings.AGENT_REGISTRY_ADDRESS), abi=ABI_AGENT_REGISTRY)
        raw = contract.functions.getAgent(agent_id).call()
        return {
            "owner": raw[0],
            "agentId": raw[1],
            "name": raw[2],
            "metadataURI": raw[3],
            "registeredAt": raw[4],
            "active": raw[5],
        }
    except Exception:
        return None


def total_agents_on_chain() -> Optional[int]:
    """AgentRegistry.totalAgents()."""
    if not settings.revive_configured or not settings.AGENT_REGISTRY_ADDRESS:
        return None
    w3 = _w3()
    if not w3:
        return None
    try:
        contract = w3.eth.contract(address=Web3.to_checksum_address(settings.AGENT_REGISTRY_ADDRESS), abi=ABI_AGENT_REGISTRY)
        return contract.functions.totalAgents().call()
    except Exception:
        return None


def get_task(task_id: int) -> Optional[dict[str, Any]]:
    """TaskMarket.getTask(taskId). status: 0=Open, 1=Accepted, 2=Completed, 3=Cancelled."""
    if not settings.revive_configured or not settings.TASK_MARKET_ADDRESS:
        return None
    w3 = _w3()
    if not w3:
        return None
    try:
        contract = w3.eth.contract(address=Web3.to_checksum_address(settings.TASK_MARKET_ADDRESS), abi=ABI_TASK_MARKET)
        raw = contract.functions.getTask(task_id).call()
        status_map = {0: "open", 1: "accepted", 2: "completed", 3: "cancelled"}
        return {
            "id": raw[0],
            "poster": raw[1],
            "posterAgentId": raw[2],
            "title": raw[3],
            "rewardAmount": raw[4],
            "reward_cog": float(Decimal(raw[4]) / (10**COG_DECIMALS)),
            "status": status_map.get(raw[5], "unknown"),
            "status_raw": int(raw[5]),
            "acceptor": raw[6],
            "acceptorAgentId": raw[7],
            "createdAt": raw[8],
            "completedAt": raw[9],
        }
    except Exception:
        return None


def next_task_id() -> Optional[int]:
    """TaskMarket.nextTaskId()."""
    if not settings.revive_configured or not settings.TASK_MARKET_ADDRESS:
        return None
    w3 = _w3()
    if not w3:
        return None
    try:
        contract = w3.eth.contract(address=Web3.to_checksum_address(settings.TASK_MARKET_ADDRESS), abi=ABI_TASK_MARKET)
        return contract.functions.nextTaskId().call()
    except Exception:
        return None


def get_reputation(agent_id: str) -> Optional[dict[str, Any]]:
    """Reputation.getReputation(agentId). Returns tasksCompleted, tasksFailed, totalCogEarned, endorsements, lastUpdated."""
    if not settings.revive_configured or not settings.REPUTATION_ADDRESS:
        return None
    w3 = _w3()
    if not w3:
        return None
    try:
        contract = w3.eth.contract(address=Web3.to_checksum_address(settings.REPUTATION_ADDRESS), abi=ABI_REPUTATION)
        raw = contract.functions.getReputation(agent_id).call()
        return {
            "tasksCompleted": raw[0],
            "tasksFailed": raw[1],
            "totalCogEarned": raw[2],
            "endorsements": raw[3],
            "lastUpdated": raw[4],
        }
    except Exception:
        return None


def get_score(agent_id: str) -> Optional[float]:
    """Reputation.getScore(agentId) returns 0-100. Map to 0-5.0 for UI star display."""
    if not settings.revive_configured or not settings.REPUTATION_ADDRESS:
        return None
    w3 = _w3()
    if not w3:
        return None
    try:
        contract = w3.eth.contract(address=Web3.to_checksum_address(settings.REPUTATION_ADDRESS), abi=ABI_REPUTATION)
        score_100 = contract.functions.getScore(agent_id).call()
        return round(score_100 * 5.0 / 100.0, 1)  # 0-100 -> 0-5.0
    except Exception:
        return None


def reputation_for_ui(agent_id: str) -> Optional[dict[str, Any]]:
    """Combined: getReputation + getScore, formatted for frontend (score 0-5.0, tasks_completed, total_cog_earned)."""
    rep = get_reputation(agent_id)
    score = get_score(agent_id)
    if rep is None and score is None:
        return None
    return {
        "score": score if score is not None else 0.0,
        "tasks_completed": int(rep["tasksCompleted"]) if rep else 0,
        "tasks_failed": int(rep["tasksFailed"]) if rep else 0,
        "total_cog_earned": float(Decimal(rep["totalCogEarned"]) / (10**COG_DECIMALS)) if rep else 0.0,
        "endorsements": int(rep["endorsements"]) if rep else 0,
    }


def _get_deployer_account():
    """Return deployer Account if REVIVE_DEPLOYER_PRIVATE_KEY is set."""
    if not settings.REVIVE_DEPLOYER_PRIVATE_KEY:
        return None
    w3 = _w3()
    if not w3:
        return None
    try:
        return w3.eth.account.from_key(settings.REVIVE_DEPLOYER_PRIVATE_KEY.strip())
    except Exception:
        return None


def _send_tx(w3: Web3, account, contract_address: str, abi: list, fn_name: str, args: tuple, gas: int = 300_000) -> Optional[str]:
    """Build, sign, send tx; return tx_hash hex or None."""
    try:
        contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=abi)
        fn = getattr(contract.functions, fn_name)(*args)
        tx = fn.build_transaction({"from": account.address, "gas": gas})
        tx["nonce"] = w3.eth.get_transaction_count(account.address)
        signed = account.sign_transaction(tx)
        tx_hash_bytes = w3.eth.send_raw_transaction(signed.raw_transaction)
        return w3.to_hex(tx_hash_bytes)
    except (ContractLogicError, ValueError, Exception):
        return None


def register_agent(agent_id: str, name: str, metadata_uri: str = "") -> Optional[str]:
    """
    AgentRegistry.register(agentId, name, metadataURI). Returns tx_hash or None.
    Uses REVIVE_DEPLOYER_PRIVATE_KEY.
    """
    if not settings.revive_configured or not settings.AGENT_REGISTRY_ADDRESS:
        return None
    account = _get_deployer_account()
    w3 = _w3()
    if not account or not w3:
        return None
    return _send_tx(
        w3, account, settings.AGENT_REGISTRY_ADDRESS, ABI_AGENT_REGISTRY,
        "register", (agent_id, name, metadata_uri or ""), 200_000,
    )


def approve_cog(spender: str, amount_wei: int) -> Optional[str]:
    """COGToken.approve(spender, amount). Returns tx_hash or None."""
    if not settings.revive_configured or not settings.COG_TOKEN_ADDRESS:
        return None
    account = _get_deployer_account()
    w3 = _w3()
    if not account or not w3:
        return None
    return _send_tx(
        w3, account, settings.COG_TOKEN_ADDRESS, ABI_COG,
        "approve", (Web3.to_checksum_address(spender), amount_wei), 100_000,
    )


def create_task_on_chain(poster_agent_id: str, title: str, reward_wei: int) -> Optional[tuple[int, str]]:
    """
    Approve TaskMarket to spend COG, then TaskMarket.createTask. Returns (chain_task_id, tx_hash) or None.
    Uses deployer as escrow payer.
    """
    if not settings.revive_configured or not settings.TASK_MARKET_ADDRESS or not settings.COG_TOKEN_ADDRESS:
        return None
    account = _get_deployer_account()
    w3 = _w3()
    if not account or not w3:
        return None
    try:
        chain_task_id = next_task_id()
        if chain_task_id is None:
            return None
        # Approve TaskMarket to pull reward_wei COG
        if not approve_cog(settings.TASK_MARKET_ADDRESS, reward_wei):
            return None
        tx_hash = _send_tx(
            w3, account, settings.TASK_MARKET_ADDRESS, ABI_TASK_MARKET,
            "createTask", (poster_agent_id, title, reward_wei), 250_000,
        )
        if not tx_hash:
            return None
        return (chain_task_id, tx_hash)
    except Exception:
        return None


def accept_task_on_chain(task_id: int, acceptor_agent_id: str) -> Optional[str]:
    """TaskMarket.acceptTask(taskId, acceptorAgentId). Returns tx_hash or None."""
    if not settings.revive_configured or not settings.TASK_MARKET_ADDRESS:
        return None
    account = _get_deployer_account()
    w3 = _w3()
    if not account or not w3:
        return None
    return _send_tx(
        w3, account, settings.TASK_MARKET_ADDRESS, ABI_TASK_MARKET,
        "acceptTask", (task_id, acceptor_agent_id), 150_000,
    )


def complete_task_on_chain(task_id: int) -> Optional[str]:
    """TaskMarket.completeTask(taskId). Returns tx_hash or None."""
    if not settings.revive_configured or not settings.TASK_MARKET_ADDRESS:
        return None
    account = _get_deployer_account()
    w3 = _w3()
    if not account or not w3:
        return None
    return _send_tx(
        w3, account, settings.TASK_MARKET_ADDRESS, ABI_TASK_MARKET,
        "completeTask", (task_id,), 150_000,
    )


def record_reputation_task_complete(agent_id: str, cog_earned_wei: int) -> Optional[str]:
    """Reputation.recordTaskComplete(agentId, cogEarned). Returns tx_hash or None."""
    if not settings.revive_configured or not settings.REPUTATION_ADDRESS:
        return None
    account = _get_deployer_account()
    w3 = _w3()
    if not account or not w3:
        return None
    return _send_tx(
        w3, account, settings.REPUTATION_ADDRESS, ABI_REPUTATION,
        "recordTaskComplete", (agent_id, cog_earned_wei), 100_000,
    )
