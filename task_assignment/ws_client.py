#!/usr/bin/env python3
"""
Example WebSocket client – tests the full pipeline end-to-end.

Usage:
  pip install websockets httpx
  python examples/ws_client.py
"""
import asyncio
import json
import httpx
import websockets

BASE_URL = "https://omnia0-smart-task-assignment.hf.space"
WS_URL = "wss://omnia0-smart-task-assignment.hf.space"

SAMPLE_TASK = {
    "description": (
        "Build a scalable FastAPI microservice with Redis caching and "
        "PostgreSQL integration. The service must handle real-time WebSocket "
        "connections and be deployed via Docker on Kubernetes. Senior-level work."
    ),
    "requester": "Product Team",
    "priority":  "High",
}


async def main():
    # 1. Submit the task → get task_id
    async with httpx.AsyncClient() as http:
        resp = await http.post(f"{BASE_URL}/analyze-task", json=SAMPLE_TASK)
        resp.raise_for_status()
        data = resp.json()

    task_id = data["task_id"]
    ws_path = data["ws_url"]
    print(f"\n✅ Task submitted  id={task_id}")
    print(f"   Connecting to {WS_URL}{ws_path} …\n")

    # 2. Connect to WebSocket and stream events
    async with websockets.connect(f"{WS_URL}{ws_path}") as ws:
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=15)
            except asyncio.TimeoutError:
                print("⏰ No message for 15 s – closing.")
                break

            msg = json.loads(raw)
            event = msg.get("event", "unknown")

            if event == "task_received":
                print(f"📥 {msg['message']}")

            elif event == "agent_start":
                print(f"🚀 {msg['message']}")

            elif event == "agent_done":
                print(f"✔  {msg['message']}")
                if "data" in msg:
                    for k, v in msg["data"].items():
                        if k not in ("agent", "status"):
                            print(f"     {k}: {v}")

            elif event == "final_result":
                fr = msg["final_result"]
                print("\n" + "═" * 60)
                print("🏆  FINAL RECOMMENDATIONS")
                print("═" * 60)
                for rec in fr["final_recommendations"]:
                    print(
                        f"  #{rec['rank']}  {rec['name']:<10} "
                        f"score={rec['final_score']:5.1f}  "
                        f"({rec['level']}, {rec['track']})"
                    )
                    print(f"       {rec['reason']}")
                    if rec['matched_skills']:
                        print(f"       skills: {', '.join(rec['matched_skills'])}")
                print("═" * 60)
                break   # pipeline finished

            else:
                print(f"ℹ  [{event}] {msg}")


if __name__ == "__main__":
    asyncio.run(main())
