"""
tests/test_transcriber.py
=========================
Unit / integration tests for the real-time STT service.

Run:
    pytest tests/ -v

Environment:
    ASSEMBLYAI_API_KEY must be set for the integration tests (marked with
    @pytest.mark.integration).  Unit tests use mocks and run without a key.
"""

from __future__ import annotations

import json
import os
import tempfile
import wave
import struct
import math
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ── import the app ──────────────────────────────────────────────────────────
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.transcriber import transcribe_file, RealtimeTranscriber

client = TestClient(app)


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_wav(path: str, duration_s: float = 0.5, freq: float = 440.0) -> None:
    """Write a minimal valid WAV file (sine wave) for testing."""
    sample_rate = 16_000
    n_samples = int(sample_rate * duration_s)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n_samples):
            value = int(32767 * math.sin(2 * math.pi * freq * i / sample_rate))
            wf.writeframes(struct.pack("<h", value))


# ── health check ─────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_schema(self):
        data = client.get("/health").json()
        assert "status" in data
        assert "api_key_configured" in data
        assert "endpoints" in data


# ── file transcription endpoint (mocked) ─────────────────────────────────────

class TestFileEndpoint:
    def _mock_result(self):
        return {
            "text": "Hello world.",
            "language": "en",
            "confidence": 0.98,
            "duration_seconds": 2.3,
        }

    def test_missing_file_returns_400(self):
        resp = client.post("/transcribe/file")
        assert resp.status_code == 422  # FastAPI validation error

    @patch("app.main.transcribe_file")
    def test_successful_upload(self, mock_tf):
        mock_tf.return_value = self._mock_result()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            _make_wav(f.name)
            tmp_path = f.name

        try:
            with open(tmp_path, "rb") as audio:
                resp = client.post(
                    "/transcribe/file",
                    files={"file": ("test.wav", audio, "audio/wav")},
                    data={"language_detection": "true", "word_timestamps": "false"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["text"] == "Hello world."
            assert data["language"] == "en"
            assert "confidence" in data
        finally:
            os.unlink(tmp_path)

    @patch("app.main.transcribe_file", side_effect=RuntimeError("AssemblyAI error"))
    def test_assemblyai_error_returns_502(self, _):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            _make_wav(f.name)
            tmp_path = f.name

        try:
            with open(tmp_path, "rb") as audio:
                resp = client.post(
                    "/transcribe/file",
                    files={"file": ("test.wav", audio, "audio/wav")},
                )
            assert resp.status_code == 502
            assert "error" in resp.json()
        finally:
            os.unlink(tmp_path)

    @patch("app.main.transcribe_file")
    def test_word_timestamps_passed_through(self, mock_tf):
        result = self._mock_result()
        result["words"] = [{"text": "Hello", "start_ms": 0, "end_ms": 400, "confidence": 0.99}]
        mock_tf.return_value = result

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            _make_wav(f.name)
            tmp_path = f.name

        try:
            with open(tmp_path, "rb") as audio:
                resp = client.post(
                    "/transcribe/file",
                    files={"file": ("test.wav", audio, "audio/wav")},
                    data={"word_timestamps": "true"},
                )
            assert resp.status_code == 200
            assert "words" in resp.json()
            _, kwargs = mock_tf.call_args
            assert kwargs.get("word_timestamps") is True
        finally:
            os.unlink(tmp_path)


# ── transcriber unit tests (mocked) ──────────────────────────────────────────

class TestTranscriberUnit:
    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("ASSEMBLYAI_API_KEY", raising=False)
        with pytest.raises(EnvironmentError, match="ASSEMBLYAI_API_KEY"):
            transcribe_file("fake.wav")

    def test_missing_file_raises(self, monkeypatch):
        monkeypatch.setenv("ASSEMBLYAI_API_KEY", "dummy")
        with pytest.raises(FileNotFoundError):
            transcribe_file("/nonexistent/path.wav")

    @patch("app.transcriber.aai.Transcriber")
    @patch("app.transcriber.aai.settings")
    def test_transcribe_file_returns_dict(self, mock_settings, MockTranscriber, monkeypatch, tmp_path):
        monkeypatch.setenv("ASSEMBLYAI_API_KEY", "dummy")

        # Build a fake transcript object
        fake_transcript = MagicMock()
        fake_transcript.status = MagicMock()
        fake_transcript.status.__eq__ = lambda self, other: False  # not error
        fake_transcript.text = "Test transcript."
        fake_transcript.language_code = "en"
        fake_transcript.confidence = 0.97
        fake_transcript.audio_duration = 1.5
        fake_transcript.words = []

        MockTranscriber.return_value.transcribe.return_value = fake_transcript

        wav = tmp_path / "test.wav"
        _make_wav(str(wav))

        result = transcribe_file(str(wav))

        assert result["text"] == "Test transcript."
        assert result["language"] == "en"
        assert result["confidence"] == 0.97
        assert result["duration_seconds"] == 1.5
        assert "words" not in result  # word_timestamps=False by default


# ── WebSocket streaming tests (mocked) ───────────────────────────────────────

class TestWebSocketEndpoint:
    def test_websocket_connects(self):
        """WebSocket handshake succeeds (mocked RealtimeTranscriber)."""
        with patch("app.main.RealtimeTranscriber") as MockRT:
            # Configure context manager
            rt_instance = AsyncMock()
            rt_instance.events = AsyncMock(return_value=aiter_from(
                [{"type": "final", "text": "Hello."}, {"type": "closed", "text": ""}]
            ))
            rt_instance.send_audio = AsyncMock()
            MockRT.return_value.__aenter__ = AsyncMock(return_value=rt_instance)
            MockRT.return_value.__aexit__ = AsyncMock(return_value=False)

            with client.websocket_connect("/transcribe/stream") as ws:
                ws.send_bytes(b"\x00" * 3200)  # send one chunk of silence
                # Just verify connection succeeded — no exception

    def test_websocket_missing_key_sends_error(self, monkeypatch):
        monkeypatch.delenv("ASSEMBLYAI_API_KEY", raising=False)
        with client.websocket_connect("/transcribe/stream") as ws:
            data = json.loads(ws.receive_text())
            assert data["type"] == "error"
            assert "ASSEMBLYAI_API_KEY" in data["text"]


# ── helper for async iteration in tests ──────────────────────────────────────

async def _agen(items):
    for item in items:
        yield item

def aiter_from(items):
    """Return an async generator function that yields items."""
    async def _inner():
        for item in items:
            yield item
    return _inner()


# ── integration tests (require real API key) ──────────────────────────────────

@pytest.mark.integration
class TestIntegration:
    """
    These tests hit the real AssemblyAI API.
    Run with: pytest tests/ -v -m integration
    Requires: ASSEMBLYAI_API_KEY to be set in the environment.
    """

    def test_file_transcription_real_api(self, tmp_path):
        wav = tmp_path / "speech.wav"
        _make_wav(str(wav), duration_s=1.0)  # silence — transcribes to empty string
        result = transcribe_file(str(wav))
        assert isinstance(result["text"], str)
        assert isinstance(result["confidence"], float)
        assert result["duration_seconds"] > 0
