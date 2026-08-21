"""Clear Mem0 memories via Mem0 REST API."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
import httpx
from dotenv import dotenv_values

ROOT_DIR = Path(__file__).resolve().parent.parent


def get_mem0_config() -> tuple[str, str | None]:
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        env_path = ROOT_DIR / "backend" / ".env"

    env = dotenv_values(env_path)
    port = env.get("MEM0_PORT", "8888")
    base_url = f"http://127.0.0.1:{port}"
    api_key = env.get("MEM0_API_KEY")
    return base_url, api_key


def clear_mem0(
    user_id: str | None = None,
    agent_id: str | None = None,
    merchant_id: str | None = None,
) -> None:
    base_url, api_key = get_mem0_config()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    if merchant_id and not agent_id:
        agent_id = f"merchant-advisor:{merchant_id}"
    if merchant_id and not user_id:
        user_id = merchant_id

    client = httpx.Client(base_url=base_url, headers=headers, timeout=10.0)

    try:
        # Check health first
        health_resp = client.get("/api/health")
        if health_resp.status_code != 200:
            print(f"⚠️ Mem0 server at {base_url} returned health status {health_resp.status_code}")
    except Exception as exc:
        print(f"❌ Cannot connect to Mem0 at {base_url}: {exc}")
        print("Make sure Docker container is running (make up / make restart)")
        sys.exit(1)

    if user_id or agent_id:
        params = {}
        if user_id:
            params["user_id"] = user_id
        if agent_id:
            params["agent_id"] = agent_id

        print(f"==> Deleting memories with filters: {params}...")
        resp = client.delete("/memories", params=params)
        if resp.status_code in (200, 204):
            print(f"✅ Successfully cleared memories for {params}!")
        else:
            print(f"❌ Failed to delete memories: HTTP {resp.status_code} - {resp.text}")
            sys.exit(1)
    else:
        print("==> Resetting ALL Mem0 memories...")
        resp = client.post("/reset")
        if resp.status_code in (200, 204):
            print("✅ Successfully cleared ALL Mem0 memories!")
        else:
            print(f"❌ Failed to reset memories: HTTP {resp.status_code} - {resp.text}")
            sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Clear Mem0 memories")
    parser.add_argument("--user-id", type=str, help="Specific user_id to clear")
    parser.add_argument("--agent-id", type=str, help="Specific agent_id to clear")
    parser.add_argument("--merchant-id", type=str, help="Specific merchant_id to clear")
    args = parser.parse_args()

    clear_mem0(
        user_id=args.user_id,
        agent_id=args.agent_id,
        merchant_id=args.merchant_id,
    )


if __name__ == "__main__":
    main()
