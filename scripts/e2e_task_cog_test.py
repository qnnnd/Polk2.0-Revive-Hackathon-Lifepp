#!/usr/bin/env python3
"""
E2E test: Task publish → accept → complete with COG flow.
Users: A = Test-Creator (0xf24F...), B = Test-Worker (0x3Cd0...).
Deployer pays on chain = A's address (backend uses deployer key = A).
Phases: (1) A publishes → check deployer COG deducted
        (2) B accepts, A completes → check B receives COG
        (3) B publishes → check deployer COG deducted again
        (4) A accepts, B completes → check A receives COG

Usage:
  python scripts/e2e_task_cog_test.py           # Full test with chain + COG checks
  python scripts/e2e_task_cog_test.py --no-chain  # API-only (reward=0), no chain/COG checks
"""
import argparse
import json
import os
import sys

try:
    import httpx
except ImportError:
    print("Install httpx: pip install httpx")
    sys.exit(1)

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8002")
API = f"{BASE_URL}/api/v1"
RPC_URL = os.environ.get("E2E_RPC_URL", "http://127.0.0.1:8545")
COG_TOKEN = os.environ.get("COG_TOKEN_ADDRESS", "0xeAB4eEBa1FF8504c124D031F6844AD98d07C318f")

ADDR_A = "0xf24FF3a9CF04c71Dbc94D0b566f7A27B94566cac"  # Test-Creator = deployer
ADDR_B = "0x3Cd0A705a2DC65e5b1E1205896BaA2be8A07c6e0"  # Test-Worker

REWARD_AB = 100.0   # A publishes, B receives
REWARD_BA = 50.0    # B publishes, A receives


def rpc(method: str, params: list) -> dict:
    r = httpx.post(RPC_URL, json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1}, timeout=10.0)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    return data.get("result")


def cog_balance(address: str) -> float:
    addr = address.lower().replace("0x", "").zfill(64)
    data_hex = "0x70a08231" + addr  # balanceOf(address)
    out = rpc("eth_call", [{"to": COG_TOKEN, "data": data_hex}, "latest"])
    if not out or out == "0x":
        return 0.0
    return int(out, 16) / 1e18


def login(username: str) -> str:
    r = httpx.post(f"{API}/auth/token", params={"username": username}, timeout=10.0)
    r.raise_for_status()
    return r.json()["access_token"]


def api_get(path: str, token: str) -> dict:
    r = httpx.get(f"{API}{path}", headers={"Authorization": f"Bearer {token}"}, timeout=10.0)
    r.raise_for_status()
    return r.json()


def api_patch(path: str, token: str, body: dict) -> dict:
    r = httpx.patch(f"{API}{path}", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json=body, timeout=10.0)
    r.raise_for_status()
    return r.json()


def api_post(path: str, token: str, body: dict = None, params: dict = None) -> dict:
    kwargs = {"headers": {"Authorization": f"Bearer {token}"}, "timeout": 30.0}
    if body is not None:
        kwargs["headers"]["Content-Type"] = "application/json"
        kwargs["json"] = body
    if params:
        kwargs["params"] = params
    r = httpx.post(f"{API}{path}", **kwargs)
    r.raise_for_status()
    return r.json() if r.content else {}


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
    if not no_chain:
        bal_a_before = cog_balance(ADDR_A)
        bal_b_before = cog_balance(ADDR_B)
        print(f"[0] COG balance  A (deployer): {bal_a_before:.2f}  B: {bal_b_before:.2f}\n")
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

    # --- Phase 1: A publishes ---
    print("[1] A publishes task (reward %.0f COG) ..." % reward_1)
    listing = api_post("/tasks", token_a, {
        "title": "E2E Test A→B",
        "description": "Task from A to B",
        "reward_cog": reward_1,
    })
    lid = listing["id"]
    chain_id = listing.get("chain_task_id")
    if not no_chain and chain_id is None:
        print("FAIL: Task has no chain_task_id (chain create failed). Check backend logs. Run with --no-chain to verify API-only.")
        sys.exit(1)
    print("    listing_id=%s chain_task_id=%s" % (lid, chain_id))

    if not no_chain:
        bal_a_after_publish = cog_balance(ADDR_A)
        expected_a = bal_a_before - REWARD_AB
        if abs(bal_a_after_publish - expected_a) > 0.01:
            print("FAIL: Deployer COG not deducted. Before=%.2f after=%.2f expected=%.2f" % (bal_a_before, bal_a_after_publish, expected_a))
            sys.exit(1)
        print("    OK: Deployer COG deducted (%.2f -> %.2f)\n" % (bal_a_before, bal_a_after_publish))
    else:
        bal_a_after_publish = bal_a_before
        print("    OK: (no chain)\n")

    # --- Phase 2: B accepts, A completes ---
    print("[2] B accepts, A completes ...")
    api_post(f"/tasks/{lid}/accept", token_b, params={"agent_id": agent_id_b})
    api_post(f"/tasks/{lid}/complete", token_a)
    if not no_chain:
        bal_b_after_first = cog_balance(ADDR_B)
        expected_b = bal_b_before + REWARD_AB
        if abs(bal_b_after_first - expected_b) > 0.01:
            print("FAIL: B did not receive COG. Before=%.2f after=%.2f expected=%.2f" % (bal_b_before, bal_b_after_first, expected_b))
            sys.exit(1)
        print("    OK: B received COG (%.2f -> %.2f)\n" % (bal_b_before, bal_b_after_first))
    else:
        bal_b_after_first = bal_b_before
        print("    OK: accept + complete\n")

    # --- Phase 3: B publishes ---
    print("[3] B publishes task (reward %.0f COG) ..." % reward_2)
    listing2 = api_post("/tasks", token_b, {
        "title": "E2E Test B→A",
        "description": "Task from B to A",
        "reward_cog": reward_2,
    })
    lid2 = listing2["id"]
    chain_id2 = listing2.get("chain_task_id")
    if not no_chain and chain_id2 is None:
        print("FAIL: Second task has no chain_task_id.")
        sys.exit(1)
    print("    listing_id=%s chain_task_id=%s" % (lid2, chain_id2))

    if not no_chain:
        bal_a_after_b_publish = cog_balance(ADDR_A)
        expected_a2 = bal_a_after_publish - REWARD_BA
        if abs(bal_a_after_b_publish - expected_a2) > 0.01:
            print("FAIL: Deployer COG not deducted on B's publish. Before=%.2f after=%.2f expected=%.2f" % (bal_a_after_publish, bal_a_after_b_publish, expected_a2))
            sys.exit(1)
        print("    OK: Deployer COG deducted again (%.2f -> %.2f)\n" % (bal_a_after_publish, bal_a_after_b_publish))
    else:
        bal_a_after_b_publish = bal_a_after_publish
        print("    OK: (no chain)\n")

    # --- Phase 4: A accepts, B completes ---
    print("[4] A accepts, B completes ...")
    api_post(f"/tasks/{lid2}/accept", token_a, params={"agent_id": agent_id_a})
    api_post(f"/tasks/{lid2}/complete", token_b)
    if not no_chain:
        bal_a_final = cog_balance(ADDR_A)
        expected_a_final = bal_a_after_b_publish + REWARD_BA
        if abs(bal_a_final - expected_a_final) > 0.01:
            print("FAIL: A did not receive COG. Before=%.2f after=%.2f expected=%.2f" % (bal_a_after_b_publish, bal_a_final, expected_a_final))
            sys.exit(1)
        print("    OK: A received COG (%.2f -> %.2f)\n" % (bal_a_after_b_publish, bal_a_final))
    else:
        bal_a_final = bal_a_after_b_publish
        print("    OK: accept + complete\n")

    print("=== All phases OK ===")
    if no_chain:
        print("(API flow only; run without --no-chain when chain accepts txs to verify COG.)")
    else:
        print("Final COG  A: %.2f  B: %.2f" % (bal_a_final, bal_b_after_first))


if __name__ == "__main__":
    main()
