#!/usr/bin/env python3
"""
End-to-end example of the AI Meeting Intelligence System.

Simulates:
  Live audio → Transcript → Translation → Task extraction →
  Assignee routing → Meeting summary → Dashboard delivery

Run against a live server:
  python example_e2e.py
"""
import asyncio
import json
import wave
import struct
import httpx
import websockets
from datetime import datetime

BASE_URL = "http://localhost:8000"
WS_BASE = "ws://localhost:8000"


async def register_and_login(name: str, email: str, password: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE_URL}/auth/register", json={
            "name": name, "email": email, "password": password
        })
        if r.status_code not in (201, 400):
            r.raise_for_status()
        r = await client.post(f"{BASE_URL}/auth/login", json={
            "email": email, "password": password
        })
        r.raise_for_status()
        return r.json()


async def create_meeting(token: str, title: str, attendee_ids: list[str]) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BASE_URL}/meeting/start",
            json={"title": title, "language": "mixed", "attendee_ids": attendee_ids},
            headers={"Authorization": f"Bearer {token}"}
        )
        r.raise_for_status()
        return r.json()


def generate_silence_pcm(duration_sec: float = 2.0, sample_rate: int = 16000) -> bytes:
    """Generate silent PCM audio bytes (simulates microphone input)."""
    num_samples = int(sample_rate * duration_sec)
    return struct.pack(f"<{num_samples}h", *([0] * num_samples))


async def stream_audio_and_receive_transcript(meeting_id: str, employee_id: str):
    """
    Simulate streaming audio to the WebSocket endpoint.
    In production, this streams real microphone PCM chunks.
    """
    uri = f"{WS_BASE}/ws/meeting/stream?meeting_id={meeting_id}&employee_id={employee_id}"
    print(f"\n[WS] Connecting to audio stream: {meeting_id}")

    received: list[dict] = []

    async with websockets.connect(uri) as ws:
        init = json.loads(await ws.recv())
        print(f"[WS] Connected: {init}")

        pcm_chunk = generate_silence_pcm(0.5)
        for i in range(6):
            await ws.send(pcm_chunk)
            print(f"[WS] Sent audio chunk {i+1}/6")
            await asyncio.sleep(0.5)

            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=0.1)
                event = json.loads(msg)
                received.append(event)
                print(f"[WS] Received: {event['event']}")
            except asyncio.TimeoutError:
                pass

        await ws.send(json.dumps({"action": "end_stream"}))
        print("[WS] Sent end_stream signal")

        try:
            final_msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            print(f"[WS] Final: {json.loads(final_msg)}")
        except asyncio.TimeoutError:
            pass

    return received


async def watch_dashboard(employee_id: str, timeout: float = 30.0) -> list[dict]:
    """Connect to the dashboard WS and collect events for `timeout` seconds."""
    uri = f"{WS_BASE}/ws/dashboard?employee_id={employee_id}"
    events: list[dict] = []
    print(f"\n[Dashboard] Watching events for employee {employee_id}")

    async with websockets.connect(uri) as ws:
        init = json.loads(await ws.recv())
        print(f"[Dashboard] Connected: {init}")
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
                event = json.loads(msg)
                events.append(event)
                print(f"[Dashboard] Event: {event['event']}")
                if event["event"] in ("meeting_ended", "summary_ready"):
                    break
        except asyncio.TimeoutError:
            pass

    return events


async def main():
    print("=" * 60)
    print("AI MEETING INTELLIGENCE SYSTEM — END-TO-END EXAMPLE")
    print("=" * 60)

    print("\n[1] Registering employees...")
    ahmed_token = (await register_and_login("Ahmed Mohamed", "ahmed@example.com", "password123"))["access_token"]
    marwa_token = (await register_and_login("Marwa Hassan", "marwa@example.com", "password123"))["access_token"]
    sara_token = (await register_and_login("Sara Ali", "sara@example.com", "password123"))["access_token"]

    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/auth/me", headers={"Authorization": f"Bearer {ahmed_token}"})
        ahmed = r.json()
        r = await client.get(f"{BASE_URL}/auth/me", headers={"Authorization": f"Bearer {marwa_token}"})
        marwa = r.json()
        r = await client.get(f"{BASE_URL}/auth/me", headers={"Authorization": f"Bearer {sara_token}"})
        sara = r.json()

    print(f"  Ahmed ID: {ahmed['id']}")
    print(f"  Marwa ID: {marwa['id']}")
    print(f"  Sara ID:  {sara['id']}")

    print("\n[2] Ahmed creates a meeting...")
    meeting = await create_meeting(
        token=ahmed_token,
        title="Q2 Sprint Planning",
        attendee_ids=[marwa["id"], sara["id"]],
    )
    print(f"  Meeting ID: {meeting['id']}")
    print(f"  Attendees: {[a['name'] for a in meeting['attendees']]}")

    print("\n[3] Streaming audio (simulated)...")
    await stream_audio_and_receive_transcript(meeting["id"], ahmed["id"])

    print("\n[4] Ahmed ends the meeting (triggers pipeline)...")
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BASE_URL}/meeting/end",
            json={"meeting_id": meeting["id"]},
            headers={"Authorization": f"Bearer {ahmed_token}"},
        )
        print(f"  Response: {r.json()}")

    print("\n[5] Waiting for pipeline to process...")
    await asyncio.sleep(15)

    print("\n[6] Checking Marwa's tasks (assigned in meeting)...")
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{BASE_URL}/employee/{marwa['id']}/tasks",
            headers={"Authorization": f"Bearer {marwa_token}"},
        )
        marwa_tasks = r.json()
        print(f"  Marwa has {len(marwa_tasks)} task(s)")
        for t in marwa_tasks:
            print(f"    - [{t['priority']}] {t['title']}")

    print("\n[7] Checking Sara's tasks (may have none)...")
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{BASE_URL}/employee/{sara['id']}/tasks",
            headers={"Authorization": f"Bearer {sara_token}"},
        )
        sara_tasks = r.json()
        print(f"  Sara has {len(sara_tasks)} task(s)")

    print("\n[8] Getting meeting summary (visible to all attendees)...")
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{BASE_URL}/meeting/{meeting['id']}/summary",
            headers={"Authorization": f"Bearer {sara_token}"},
        )
        if r.status_code == 200:
            summary = r.json()
            print(f"  Overview: {summary['overview'][:200]}")
            print(f"  Key points: {len(summary['key_points'])}")
            print(f"  Decisions: {len(summary['decisions'])}")
        else:
            print(f"  Summary status: {r.status_code}")

    print("\n" + "=" * 60)
    print("EXAMPLE COMPLETE")
    print("=" * 60)
    print("""
FLOW SUMMARY:
  Live Audio
    ↓
  WebSocket stream → AssemblyAI transcription
    ↓
  Real-time Arabic + English translation (per segment)
    ↓
  Transcript stored in Redis buffer
    ↓
  Meeting end signal → Redis pub/sub
    ↓
  MeetingEndPipeline triggered:
    [1] Aggregate transcript from Redis
    [2] Translate full transcript to Arabic
    [3] Persist Transcript table
    [4] Extract tasks via Groq LLM (llama-3.3-70b)
    [5] Resolve assignees (NER + LLM fuzzy match)
    [6] Save Task rows to PostgreSQL
    [7] Push each task ONLY to assigned employee via WebSocket
    [8] Generate meeting summary via Groq LLM
    [9] Push summary to ALL attendees via WebSocket
    [10] Mark meeting COMPLETED

TASK DELIVERY:
  Ahmed dashboard  → his tasks only
  Marwa dashboard  → her tasks only
  Sara dashboard   → her tasks only (or empty if unassigned)
  ALL dashboards   → meeting summary
""")


if __name__ == "__main__":
    asyncio.run(main())
