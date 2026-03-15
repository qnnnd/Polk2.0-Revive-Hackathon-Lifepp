#!/usr/bin/env python3
"""
E2E test: Task publish → accept → complete with native IVE flow.
Publisher pays: createTask is signed by the publisher (A or B); accept/complete by backend relayer.
Users: A = Test-Creator (0xf24F...), B = Test-Worker (0x3Cd0...).
Phases: (1) A publishes → check publisher A IVE deducted
        (2) B accepts, A completes → check B receives IVE
        (3) B publishes → check publisher B IVE deducted
        (4) A accepts, B completes → check A receives IVE

Usage:
  E2E_PUBLISHER_A_PRIVATE_KEY=0x... E2E_PUBLISHER_B_PRIVATE_KEY=0x... python scripts/e2e_task_cog_test.py
  Or run from backend with venv (has web3): cd backend && .venv/bin/python ../scripts/e2e_task_cog_test.py
  Keys: A = Alith (deployer), B = Baltathar. Or set only A for phases 1-2.
  python scripts/e2e_task_cog_test.py --no-chain  # API-only (reward=0), no chain checks
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

def _load_env_key(name: str, fallback_path: str = None) -> str:
    v = os.environ.get(name)
    if v:
        return v.strip()
    if fallback_path and os.path.isfile(fallback_path):
        with open(fallback_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("REVIVE_DEPLOYER_PRIVATE_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""

def _send_create_task_tx(chain_tx_params: dict, publisher_private_key: str) -> str:
    """Sign createTask with publisher key and send via RPC. Returns tx_hash hex."""
    try:
        from eth_account import Account
    except ImportError:
        print("FAIL: eth_account required. Run from backend venv: cd backend && .venv/bin/python ../scripts/e2e_task_cog_test.py")
        sys.exit(1)
    to = chain_tx_params["to"]
    data = chain_tx_params["data"]
    if not data.startswith("0x"):
        data = "0x" + data
    value_hex = chain_tx_params["value"]
    if not value_hex.startswith("0x"):
        value_hex = "0x" + value_hex
    chain_id = int(chain_tx_params["chain_id"])
    account = Account.from_key(publisher_private_key)
    nonce_hex = rpc("eth_getTransactionCount", [account.address, "latest"])
    gas_price_hex = rpc("eth_gasPrice", [])
    nonce = int(nonce_hex, 16)
    gas_price = int(gas_price_hex, 16)
    gas_limit = 2_000_000
    tx = {
        "nonce": nonce,
        "gasPrice": gas_price,
        "gas": gas_limit,
        "to": to,
        "value": int(value_hex, 16),
        "data": data,
        "chainId": chain_id,
    }
    signed = account.sign_transaction(tx)
    raw_hex = signed.raw_transaction.hex()
    if not raw_hex.startswith("0x"):
        raw_hex = "0x" + raw_hex
    tx_hash = rpc("eth_sendRawTransaction", [raw_hex])
    return tx_hash if isinstance(tx_hash, str) else ("0x" + tx_hash.hex()) if hasattr(tx_hash, "hex") else str(tx_hash)

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8002")
API = f"{BASE_URL}/api/v1"
RPC_URL = os.environ.get("E2E_RPC_URL", "http://127.0.0.1:8545")

ADDR_A = "0xf24FF3a9CF04c71Dbc94D0b566f7A27B94566cac"  # Test-Creator = deployer
ADDR_B = "0x3Cd0A705a2DC65e5b1E1205896BaA2be8A07c6e0"  # Test-Worker

REWARD_AB = 100.0   # A publishes, B receives
REWARD_BA = 50.0    # B publishes, A receives


def rpc(method: str, params: list) -> dict:
    # Use urllib for RPC (some envs return 502 for httpx to localhost:8545)
    payload = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
    req = urllib.request.Request(RPC_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    if "error" in data:
        raise RuntimeError(data["error"])
    return data.get("result")


def ive_balance(address: str) -> float:
    """Native IVE balance of address (ether units)."""
    out = rpc("eth_getBalance", [address, "latest"])
    if not out or out == "0x":
        return 0.0
    return int(out, 16) / 1e18


def login(username: str) -> str:
    req = urllib.request.Request(
        f"{API}/auth/token?username={urllib.parse.quote(username, safe='')}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())["access_token"]


def api_get(path: str, token: str) -> dict:
    req = urllib.request.Request(f"{API}{path}", headers={"Authorization": f"Bearer {token}"}, method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def api_patch(path: str, token: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else {}


def api_post(path: str, token: str, body: dict = None, params: dict = None) -> dict:
    url = f"{API}{path}"
    if params:
        url = f"{url}?{'&'.join(f'{k}={urllib.parse.quote(str(v))}' for k,v in params.items())}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Authorization": f"Bearer {token}"}, method="POST")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else {}


def main():
    parser = argparse.ArgumentParser(description="E2E task + COG flow")
    parser.add_argument("--no-chain", action="store_true", help="Use reward=0 (no chain), only verify API flow")
    args = parser.parse_args()
    no_chain = args.no_chain

    print("=== E2E Task + COG flow ===\n")
    if no_chain:
        print("Mode: --no-chain (reward=0, no chain/COG checks)\n")
    print(f"API: {API}  RPC: {RPC_URL}\n")

    # --- Phase 0: balances before (skip if no-chain) ---
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_env = os.path.join(script_dir, "..", "backend", ".env")
    key_a = _load_env_key("E2E_PUBLISHER_A_PRIVATE_KEY", backend_env)
    key_b = _load_env_key("E2E_PUBLISHER_B_PRIVATE_KEY")
    if not no_chain and (not key_a or not key_b):
        print("WARN: Set E2E_PUBLISHER_A_PRIVATE_KEY and E2E_PUBLISHER_B_PRIVATE_KEY for full chain test (or run from backend with .env).")
    if not no_chain:
        bal_a_before = ive_balance(ADDR_A)
        bal_b_before = ive_balance(ADDR_B)
        print(f"[0] IVE balance  A (publisher): {bal_a_before:.2f}  B: {bal_b_before:.2f}\n")
    else:
        bal_a_before = bal_b_before = 0.0

    token_a = login("Test-Creator")
    token_b = login("Test-Worker")
    api_patch("/auth/me", token_a, {"wallet_address": ADDR_A})
    api_patch("/auth/me", token_b, {"wallet_address": ADDR_B})

    agents_a = api_get("/agents", token_a)
    agents_b = api_get("/agents", token_b)
    if not agents_a.get("agents"):
        print("FAIL: Test-Creator has no agents")
        sys.exit(1)
    if not agents_b.get("agents"):
        print("FAIL: Test-Worker has no agents")
        sys.exit(1)
    agent_id_a = str(agents_a["agents"][0]["id"])
    agent_id_b = str(agents_b["agents"][0]["id"])
    print(f"Agent A: {agent_id_a}  Agent B: {agent_id_b}\n")

    reward_1 = 0.0 if no_chain else REWARD_AB
    reward_2 = 0.0 if no_chain else REWARD_BA

    # --- Phase 1: A publishes (publisher A pays on chain) ---
    print("[1] A publishes task (reward %.0f IVE) ..." % reward_1)
    listing = api_post("/tasks", token_a, {
        "title": "E2E Test A→B",
        "description": "Task from A to B",
        "reward_cog": reward_1,
    })
    lid = listing["id"]
    if not no_chain and listing.get("chain_tx_params") and not listing.get("chain_task_id"):
        if not key_a:
            print("FAIL: chain_tx_params returned but E2E_PUBLISHER_A_PRIVATE_KEY not set. Set it or run from backend with .env.")
            sys.exit(1)
        print("    Signing createTask as publisher A ...")
        tx_hash = _send_create_task_tx(listing["chain_tx_params"], key_a)
        print("    tx_hash=%s" % (tx_hash[:18] + "..." if len(tx_hash) > 18 else tx_hash))
        time.sleep(2)
        updated = api_patch(f"/tasks/{lid}/chain_created", token_a, {"tx_hash": tx_hash})
        listing = updated
        chain_id = listing.get("chain_task_id")
        if chain_id is None:
            print("FAIL: PATCH chain_created did not set chain_task_id.")
            sys.exit(1)
    chain_id = listing.get("chain_task_id")
    if not no_chain and chain_id is None:
        print("FAIL: Task has no chain_task_id (chain create failed). Check backend logs or set E2E_PUBLISHER_A_PRIVATE_KEY.")
        sys.exit(1)
    print("    listing_id=%s chain_task_id=%s" % (lid, chain_id))

    if not no_chain:
        bal_a_after_publish = ive_balance(ADDR_A)
        deducted = bal_a_before - bal_a_after_publish
        if deducted < REWARD_AB - 10:  # allow up to 10 IVE gas tolerance
            print("FAIL: Publisher A IVE not deducted. Before=%.2f after=%.2f deducted=%.2f (expected >= %.0f)" % (bal_a_before, bal_a_after_publish, deducted, REWARD_AB))
            sys.exit(1)
        print("    OK: Publisher A IVE deducted (%.2f -> %.2f, deducted %.2f)\n" % (bal_a_before, bal_a_after_publish, deducted))
    else:
        bal_a_after_publish = bal_a_before
        print("    OK: (no chain)\n")

    # --- Phase 2: B accepts, A completes ---
    print("[2] B accepts, A completes ...")
    api_post(f"/tasks/{lid}/accept", token_b, params={"agent_id": agent_id_b})
    time.sleep(5)
    for attempt in range(3):
        try:
            api_post(f"/tasks/{lid}/complete", token_a)
            break
        except urllib.error.HTTPError as e:
            if e.code == 503 and attempt < 2:
                wait = 15 * (attempt + 1)
                print("    complete returned 503, retrying in %ss ..." % wait)
                time.sleep(wait)
            else:
                raise
    if not no_chain:
        bal_b_after_first = ive_balance(ADDR_B)
        received = bal_b_after_first - bal_b_before
        if received < REWARD_AB - 0.01:
            print("FAIL: B did not receive IVE. Before=%.2f after=%.2f received=%.2f (expected >= %.0f)" % (bal_b_before, bal_b_after_first, received, REWARD_AB))
            sys.exit(1)
        print("    OK: B received IVE (%.2f -> %.2f, +%.2f)\n" % (bal_b_before, bal_b_after_first, received))
    else:
        bal_b_after_first = bal_b_before
        print("    OK: accept + complete\n")

    # --- Phase 3: B publishes (publisher B pays on chain) ---
    print("[3] B publishes task (reward %.0f IVE) ..." % reward_2)
    listing2 = api_post("/tasks", token_b, {
        "title": "E2E Test B→A",
        "description": "Task from B to A",
        "reward_cog": reward_2,
    })
    lid2 = listing2["id"]
    if not no_chain and listing2.get("chain_tx_params") and not listing2.get("chain_task_id"):
        if not key_b:
            print("FAIL: chain_tx_params returned but E2E_PUBLISHER_B_PRIVATE_KEY not set. Skipping phase 3-4 chain check.")
            bal_a_after_b_publish = bal_a_after_publish
        else:
            print("    Signing createTask as publisher B ...")
            tx_hash2 = _send_create_task_tx(listing2["chain_tx_params"], key_b)
            print("    tx_hash=%s" % (tx_hash2[:18] + "..." if len(tx_hash2) > 18 else tx_hash2))
            time.sleep(2)
            listing2 = api_patch(f"/tasks/{lid2}/chain_created", token_b, {"tx_hash": tx_hash2})
    chain_id2 = listing2.get("chain_task_id")
    if not no_chain and chain_id2 is None and key_b:
        print("FAIL: Second task has no chain_task_id.")
        sys.exit(1)
    print("    listing_id=%s chain_task_id=%s" % (lid2, chain_id2))

    if not no_chain:
        bal_b_after_publish = ive_balance(ADDR_B)
        deducted2 = bal_b_after_first - bal_b_after_publish
        if key_b and deducted2 < REWARD_BA - 10:
            print("FAIL: Publisher B IVE not deducted. Before=%.2f after=%.2f deducted=%.2f (expected >= %.0f)" % (bal_b_after_first, bal_b_after_publish, deducted2, REWARD_BA))
            sys.exit(1)
        if key_b:
            print("    OK: Publisher B IVE deducted (%.2f -> %.2f, deducted %.2f)\n" % (bal_b_after_first, bal_b_after_publish, deducted2))
        else:
            print("    OK: (B key not set, skip publisher B deduct check)\n")
        bal_a_after_b_publish = bal_a_after_publish
    else:
        bal_a_after_b_publish = bal_a_after_publish
        print("    OK: (no chain)\n")

    # --- Phase 4: A accepts, B completes ---
    print("[4] A accepts, B completes ...")
    api_post(f"/tasks/{lid2}/accept", token_a, params={"agent_id": agent_id_a})
    time.sleep(5)
    try:
        api_post(f"/tasks/{lid2}/complete", token_b)
    except urllib.error.HTTPError as e:
        if e.code == 503:
            print("    complete returned 503, retrying in 30s ...")
            time.sleep(30)
            api_post(f"/tasks/{lid2}/complete", token_b)
        else:
            raise
    if not no_chain:
        bal_a_final = ive_balance(ADDR_A)
        received_a = bal_a_final - bal_a_after_b_publish
        if chain_id2 is not None and received_a < REWARD_BA - 0.01:
            print("FAIL: A did not receive IVE. Before=%.2f after=%.2f received=%.2f (expected >= %.0f)" % (bal_a_after_b_publish, bal_a_final, received_a, REWARD_BA))
            sys.exit(1)
        if chain_id2 is not None:
            print("    OK: A received IVE (%.2f -> %.2f, +%.2f)\n" % (bal_a_after_b_publish, bal_a_final, received_a))
        else:
            print("    OK: accept + complete (no chain task for second listing)\n")
    else:
        bal_a_final = bal_a_after_b_publish
        print("    OK: accept + complete\n")

    print("=== All phases OK ===")
    if no_chain:
        print("(API flow only; run without --no-chain when chain accepts txs to verify IVE.)")
    else:
        b_final = bal_b_after_publish if not no_chain else bal_b_after_first
        print("Final IVE  A: %.2f  B: %.2f" % (bal_a_final, b_final))


if __name__ == "__main__":
    main()
