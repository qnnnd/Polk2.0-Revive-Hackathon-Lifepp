"""
Life++ — Revive testnet chain service (read-only + optional writes).
Uses web3.py for AgentRegistry, TaskMarket (native IVE), Reputation.
All chain-derived data for 13.4 compliance must go through this service.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Optional

from web3 import Web3
from web3.exceptions import ContractLogicError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Native IVE (same decimals as ETH)
IVE_DECIMALS = 18


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
        {"name": "rewardRecipient", "type": "address"},
        {"name": "createdAt", "type": "uint256"},
        {"name": "completedAt", "type": "uint256"},
    ], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "nextTaskId", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "posterAgentId", "type": "string"}, {"name": "title", "type": "string"}, {"name": "rewardAmount", "type": "uint256"}], "name": "createTask", "outputs": [{"type": "uint256"}], "stateMutability": "payable", "type": "function"},
    {"inputs": [{"name": "taskId", "type": "uint256"}, {"name": "acceptorAgentId", "type": "string"}, {"name": "rewardRecipient", "type": "address"}], "name": "acceptTask", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
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
    """Native IVE balance of address in human units (not wei)."""
    if not settings.revive_configured:
        return None
    w3 = _w3()
    if not w3 or not address:
        return None
    try:
        wei = w3.eth.get_balance(Web3.to_checksum_address(address))
        return Decimal(wei) / (10**IVE_DECIMALS)
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
            "reward_cog": float(Decimal(raw[4]) / (10**IVE_DECIMALS)),
            "status": status_map.get(raw[5], "unknown"),
            "status_raw": int(raw[5]),
            "acceptor": raw[6],
            "acceptorAgentId": raw[7],
            "rewardRecipient": raw[8],
            "createdAt": raw[9],
            "completedAt": raw[10],
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
        "total_cog_earned": float(Decimal(rep["totalCogEarned"]) / (10**IVE_DECIMALS)) if rep else 0.0,
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


def deployer_native_balance_wei() -> Optional[int]:
    """Native IVE balance of the deployer account in wei. Returns None if not configured or RPC error."""
    account = _get_deployer_account()
    if not account:
        return None
    if not settings.revive_configured:
        return None
    w3 = _w3()
    if not w3:
        return None
    try:
        return w3.eth.get_balance(Web3.to_checksum_address(account.address))
    except Exception:
        return None


def _send_tx(w3: Web3, account, contract_address: str, abi: list, fn_name: str, args: tuple, gas: int = 300_000, value_wei: int = 0) -> Optional[str]:
    """Build, sign, send tx; return tx_hash hex or None. value_wei for payable (e.g. createTask with IVE)."""
    try:
        contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=abi)
        fn = getattr(contract.functions, fn_name)(*args)
        chain_id = w3.eth.chain_id
        gas_price = w3.eth.gas_price
        base = {"from": account.address, "gas": gas, "chainId": chain_id, "value": value_wei}
        if gas_price and gas_price > 0:
            base["gasPrice"] = gas_price
        tx = fn.build_transaction(base)
        tx["nonce"] = w3.eth.get_transaction_count(account.address)
        signed = account.sign_transaction(tx)
        tx_hash_bytes = w3.eth.send_raw_transaction(signed.raw_transaction)
        return w3.to_hex(tx_hash_bytes)
    except (ContractLogicError, ValueError, Exception) as e:
        logger.warning("_send_tx %s(%s) failed: %s", fn_name, contract_address[:10], e)
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


def create_task_on_chain(poster_agent_id: str, title: str, reward_wei: int) -> Optional[tuple[int, str]]:
    """
    TaskMarket.createTask with native IVE (msg.value). Returns (chain_task_id, tx_hash) or None.
    Uses deployer as escrow payer; deployer must have enough IVE for reward + gas.
    """
    if not settings.revive_configured or not settings.TASK_MARKET_ADDRESS:
        logger.warning("create_task_on_chain: skip (revive not configured or missing TASK_MARKET)")
        return None
    account = _get_deployer_account()
    w3 = _w3()
    if not account or not w3:
        logger.warning("create_task_on_chain: skip (no deployer account or w3; set REVIVE_DEPLOYER_PRIVATE_KEY and REVIVE_RPC_URL)")
        return None
    try:
        chain_task_id = next_task_id()
        if chain_task_id is None:
            logger.warning("create_task_on_chain: next_task_id() returned None")
            return None
        tx_hash = _send_tx(
            w3, account, settings.TASK_MARKET_ADDRESS, ABI_TASK_MARKET,
            "createTask", (poster_agent_id, title, reward_wei), 250_000, value_wei=reward_wei,
        )
        if not tx_hash:
            logger.warning("create_task_on_chain: createTask tx failed (check deployer IVE balance and gas)")
            return None
        logger.info("create_task_on_chain: ok chain_task_id=%s tx_hash=%s", chain_task_id, tx_hash)
        return (chain_task_id, tx_hash)
    except Exception as e:
        logger.exception("create_task_on_chain: exception %s", e)
        return None


def accept_task_on_chain(task_id: int, acceptor_agent_id: str, reward_recipient_address: str) -> Optional[str]:
    """TaskMarket.acceptTask(taskId, acceptorAgentId, rewardRecipient). reward_recipient_address = claimer's wallet (receives COG on complete). Returns tx_hash or None."""
    if not settings.revive_configured or not settings.TASK_MARKET_ADDRESS:
        logger.warning("accept_task_on_chain: skip (revive not configured or no TASK_MARKET)")
        return None
    if not reward_recipient_address or not reward_recipient_address.strip():
        logger.warning("accept_task_on_chain: skip (empty reward_recipient_address)")
        return None
    account = _get_deployer_account()
    w3 = _w3()
    if not account or not w3:
        logger.warning("accept_task_on_chain: skip (no deployer or w3)")
        return None
    try:
        recipient = Web3.to_checksum_address(reward_recipient_address.strip())
    except Exception as e:
        logger.warning("accept_task_on_chain: invalid reward_recipient_address %s", e)
        return None
    tx_hash = _send_tx(
        w3, account, settings.TASK_MARKET_ADDRESS, ABI_TASK_MARKET,
        "acceptTask", (task_id, acceptor_agent_id, recipient), 150_000,
    )
    if tx_hash:
        logger.info("accept_task_on_chain: ok task_id=%s reward_recipient=%s tx_hash=%s", task_id, recipient, tx_hash)
    else:
        logger.warning("accept_task_on_chain: acceptTask tx failed for task_id=%s", task_id)
    return tx_hash


def complete_task_on_chain(task_id: int) -> Optional[str]:
    """TaskMarket.completeTask(taskId). Returns tx_hash or None."""
    if not settings.revive_configured or not settings.TASK_MARKET_ADDRESS:
        logger.warning("complete_task_on_chain: skip (revive not configured or no TASK_MARKET)")
        return None
    account = _get_deployer_account()
    w3 = _w3()
    if not account or not w3:
        logger.warning("complete_task_on_chain: skip (no deployer or w3)")
        return None
    tx_hash = _send_tx(
        w3, account, settings.TASK_MARKET_ADDRESS, ABI_TASK_MARKET,
        "completeTask", (task_id,), 150_000,
    )
    if tx_hash:
        logger.info("complete_task_on_chain: ok task_id=%s tx_hash=%s", task_id, tx_hash)
    else:
        logger.warning("complete_task_on_chain: completeTask tx failed for task_id=%s (task may not be Accepted on chain)", task_id)
    return tx_hash


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
