"""
Life++ — Revive testnet chain service (read-only + optional writes).
Uses web3.py for AgentRegistry, TaskMarket (native IVE), Reputation.
All chain-derived data for 13.4 compliance must go through this service.
"""
from __future__ import annotations

import logging
import time
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
# Include TaskCreated event so we can parse taskId from createTask tx receipt reliably.
ABI_TASK_MARKET = [
    {"anonymous": False, "inputs": [
        {"indexed": True, "name": "taskId", "type": "uint256"},
        {"indexed": True, "name": "poster", "type": "address"},
        {"indexed": False, "name": "reward", "type": "uint256"},
    ], "name": "TaskCreated", "type": "event"},
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
    {"inputs": [{"name": "taskId", "type": "uint256"}, {"name": "acceptorAgentId", "type": "string"}, {"name": "rewardRecipient", "type": "address"}, {"name": "acceptorAddress", "type": "address"}], "name": "acceptTaskFor", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "taskId", "type": "uint256"}], "name": "completeTask", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "taskId", "type": "uint256"}], "name": "completeTaskFor", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
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


def wait_for_receipt(tx_hash_hex: str, timeout_seconds: int = 60) -> bool:
    """Wait for transaction to be mined. Returns True if succeeded (status 1 or 0x1), False on timeout or revert."""
    w3 = _w3()
    if not w3:
        return False
    try:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash_hex, timeout=timeout_seconds)
        return _receipt_succeeded(receipt)
    except Exception as e:
        logger.warning("wait_for_receipt %s: %s", tx_hash_hex[:18] if tx_hash_hex else "", e)
        return False


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
    """Build, sign, send tx; return tx_hash hex or None. Auto-estimates gas with 1.3x buffer for Revive/PolkaVM."""
    try:
        contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=abi)
        fn = getattr(contract.functions, fn_name)(*args)
        chain_id = w3.eth.chain_id
        gas_price = w3.eth.gas_price
        call_params = {"from": account.address, "value": value_wei}
        try:
            gas = int(fn.estimate_gas(call_params) * 1.3)
        except Exception as est_err:
            logger.warning("_send_tx %s: estimate_gas failed (%s), using fallback %s", fn_name, est_err, gas)
        base = {**call_params, "gas": gas, "chainId": chain_id}
        if gas_price and gas_price > 0:
            base["gasPrice"] = gas_price
        tx = fn.build_transaction(base)
        tx["nonce"] = w3.eth.get_transaction_count(account.address)
        signed = account.sign_transaction(tx)
        try:
            tx_hash_bytes = w3.eth.send_raw_transaction(signed.raw_transaction)
        except Exception as send_err:
            if "1012" in str(send_err) or "temporarily banned" in str(send_err).lower():
                logger.warning("_send_tx %s: 1012/temporarily banned, waiting 5s and retrying once", fn_name)
                time.sleep(5)
                tx["nonce"] = w3.eth.get_transaction_count(account.address)
                signed = account.sign_transaction(tx)
                tx_hash_bytes = w3.eth.send_raw_transaction(signed.raw_transaction)
            else:
                raise
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


def get_create_task_tx_params(poster_agent_id: str, title: str, reward_wei: int) -> Optional[dict]:
    """
    Build createTask tx params for the publisher to sign (e.g. in MetaMask).
    Returns dict with to, data, value (hex), chain_id so frontend can eth_sendTransaction.
    Only requires TASK_MARKET_ADDRESS and a working RPC (not full revive_configured).
    """
    if not settings.TASK_MARKET_ADDRESS or not settings.TASK_MARKET_ADDRESS.strip():
        logger.warning("get_create_task_tx_params: TASK_MARKET_ADDRESS not set (run scripts/apply-revive-local-env.sh)")
        return None
    w3 = _w3()
    if not w3:
        logger.warning("get_create_task_tx_params: no RPC (set REVIVE_RPC_URL or use default http://127.0.0.1:8545)")
        return None
    try:
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(settings.TASK_MARKET_ADDRESS),
            abi=ABI_TASK_MARKET,
        )
        fn = contract.functions.createTask(poster_agent_id, title, reward_wei)
        data_raw = fn._encode_transaction_data()
        data_hex = data_raw.hex() if hasattr(data_raw, "hex") else data_raw
        if not data_hex.startswith("0x"):
            data_hex = "0x" + data_hex
        return {
            "to": settings.TASK_MARKET_ADDRESS,
            "data": data_hex,
            "value": hex(reward_wei),
            "chain_id": w3.eth.chain_id,
        }
    except Exception as e:
        logger.warning("get_create_task_tx_params failed: %s", e, exc_info=True)
        return None


def _receipt_succeeded(receipt: dict) -> bool:
    """True if receipt indicates success (handles int 1 or hex string 0x1)."""
    s = receipt.get("status")
    if s is None:
        return False
    if s == 1:
        return True
    if isinstance(s, str) and s in ("0x1", "0x01"):
        return True
    return False


def get_task_id_from_create_tx(tx_hash_hex: str, timeout_seconds: int = 60) -> Optional[int]:
    """
    Wait for createTask tx receipt and parse TaskCreated event to get taskId.
    Uses contract event decoding first (reliable); falls back to manual topics parsing.
    """
    if not settings.TASK_MARKET_ADDRESS or not settings.TASK_MARKET_ADDRESS.strip():
        return None
    w3 = _w3()
    if not w3:
        return None
    tx_hash_hex = tx_hash_hex.strip()
    if not tx_hash_hex.startswith("0x"):
        tx_hash_hex = "0x" + tx_hash_hex
    try:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash_hex, timeout=timeout_seconds)
        if not _receipt_succeeded(receipt):
            logger.warning("get_task_id_from_create_tx: tx failed status=%s", receipt.get("status"))
            return None

        task_market = Web3.to_checksum_address(settings.TASK_MARKET_ADDRESS)
        contract = w3.eth.contract(address=task_market, abi=ABI_TASK_MARKET)

        # Method 1: decode via contract event (most reliable)
        try:
            processed = contract.events.TaskCreated().process_receipt(receipt)
            if processed:
                args = processed[0].args
                task_id = getattr(args, "taskId", None) or (args[0] if isinstance(args, (list, tuple)) else None)
                if task_id is not None:
                    task_id = int(task_id)
                    logger.info("get_task_id_from_create_tx: taskId=%s from TaskCreated event", task_id)
                    return task_id
        except Exception as decode_err:
            logger.debug("get_task_id_from_create_tx: process_receipt failed %s, trying manual parse", decode_err)

        # Method 2: manual topics (TaskCreated: topics[0]=sig, topics[1]=taskId, topics[2]=poster)
        task_market_lower = settings.TASK_MARKET_ADDRESS.strip().lower()
        logs = receipt.get("logs") or receipt.get("log") or []
        for log in logs:
            addr = log.get("address")
            if not addr or addr.lower() != task_market_lower:
                continue
            topics = log.get("topics") or []
            if len(topics) >= 2:
                task_id = int(topics[1], 16)
                logger.info("get_task_id_from_create_tx: taskId=%s from topics", task_id)
                return task_id

        # Retry once (Revive may index logs slightly later)
        logger.warning("get_task_id_from_create_tx: no TaskCreated in receipt, retry in 3s")
        time.sleep(3)
        receipt = w3.eth.get_transaction_receipt(tx_hash_hex)
        if not receipt or not _receipt_succeeded(receipt):
            return None
        try:
            processed = contract.events.TaskCreated().process_receipt(receipt)
            if processed:
                args = processed[0].args
                tid = getattr(args, "taskId", None) or (args[0] if isinstance(args, (list, tuple)) else None)
                if tid is not None:
                    return int(tid)
        except Exception:
            pass
        logs = receipt.get("logs") or receipt.get("log") or []
        for log in logs:
            addr = log.get("address")
            if not addr or addr.lower() != task_market_lower:
                continue
            topics = log.get("topics") or []
            if len(topics) >= 2:
                return int(topics[1], 16)
        logger.warning("get_task_id_from_create_tx: no TaskCreated after retry (receipt keys=%s)", list(receipt.keys()) if receipt else None)
        return None
    except Exception as e:
        logger.warning("get_task_id_from_create_tx %s: %s", tx_hash_hex[:18], e)
        return None


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
    """TaskMarket.acceptTaskFor(...). reward_recipient_address = claimer's wallet (receives IVE on complete). Returns tx_hash or None."""
    if not settings.TASK_MARKET_ADDRESS or not settings.TASK_MARKET_ADDRESS.strip():
        logger.warning("accept_task_on_chain: skip (no TASK_MARKET_ADDRESS)")
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
        "acceptTaskFor", (task_id, acceptor_agent_id, recipient, recipient), 500_000,
    )
    if tx_hash:
        logger.info("accept_task_on_chain: ok task_id=%s reward_recipient=%s tx_hash=%s", task_id, recipient, tx_hash)
    else:
        logger.warning("accept_task_on_chain: acceptTask tx failed for task_id=%s", task_id)
    return tx_hash


def complete_task_on_chain(task_id: int) -> Optional[str]:
    """TaskMarket.completeTaskFor/completeTask(taskId). Sends IVE to rewardRecipient. Returns tx_hash or None."""
    if not settings.TASK_MARKET_ADDRESS or not settings.TASK_MARKET_ADDRESS.strip():
        logger.warning("complete_task_on_chain: skip (no TASK_MARKET_ADDRESS)")
        return None
    account = _get_deployer_account()
    w3 = _w3()
    if not account or not w3:
        logger.warning("complete_task_on_chain: skip (no deployer or w3)")
        return None
    logger.info("complete_task_on_chain: sender=%s task_id=%s (must be contract relayer/poster)", account.address, task_id)

    # Fetch task from chain directly (no revive_configured dependency) so idempotency and deployer_is_poster work.
    on_chain: Optional[dict[str, Any]] = None
    try:
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(settings.TASK_MARKET_ADDRESS),
            abi=ABI_TASK_MARKET,
        )
        raw = contract.functions.getTask(task_id).call()
        status_map = {0: "open", 1: "accepted", 2: "completed", 3: "cancelled"}
        on_chain = {"status": status_map.get(raw[5], "unknown"), "poster": raw[1]}
    except Exception as e:
        logger.warning("complete_task_on_chain: getTask(task_id=%s) failed: %s", task_id, e)

    # Idempotency: if task already completed on-chain, treat as success.
    if on_chain and on_chain.get("status") == "completed":
        logger.info("complete_task_on_chain: task_id=%s already completed on chain (idempotent)", task_id)
        # Sentinel hash indicating success without new tx (not a real tx hash but signals ok to caller).
        return "0x" + "0" * 63 + "1"

    # Prefer completeTask when deployer is also the poster; otherwise use completeTaskFor as relayer.
    deployer_is_poster = (
        on_chain is not None
        and str(on_chain.get("poster", "")).lower() == account.address.lower()
    )
    fn_name = "completeTask" if deployer_is_poster else "completeTaskFor"
    logger.info("complete_task_on_chain: using %s (deployer_is_poster=%s)", fn_name, deployer_is_poster)

    tx_hash: Optional[str] = None

    # Primary attempts with chosen function (with retries and gas bump).
    for delay, gas in ((0, 500_000), (5, 500_000), (8, 800_000)):
        if delay:
            time.sleep(delay)
        tx_hash = _send_tx(
            w3,
            account,
            settings.TASK_MARKET_ADDRESS,
            ABI_TASK_MARKET,
            fn_name,
            (task_id,),
            gas,
        )
        if tx_hash:
            break

    # Fallback: if relayer path failed and deployer is not poster, try direct poster-style completeTask.
    if not tx_hash and not deployer_is_poster:
        logger.warning(
            "complete_task_on_chain: %s failed, trying completeTask fallback for task_id=%s",
            fn_name,
            task_id,
        )
        tx_hash = _send_tx(
            w3,
            account,
            settings.TASK_MARKET_ADDRESS,
            ABI_TASK_MARKET,
            "completeTask",
            (task_id,),
            500_000,
        )

    if tx_hash:
        ok = wait_for_receipt(tx_hash, 60)
        if not ok:
            logger.warning("complete_task_on_chain: completeTask tx reverted for task_id=%s", task_id)
            return None
        logger.info("complete_task_on_chain: ok task_id=%s tx_hash=%s", task_id, tx_hash)
    else:
        logger.warning(
            "complete_task_on_chain: completeTask tx failed for task_id=%s (task may not be Accepted on chain)",
            task_id,
        )
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
