"""
Test suite for the AI Meeting Intelligence System.
Run with: pytest tests/ -v
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_transcript():
    return """
    Ahmed: Good morning everyone. Let's go over the sprint.
    Marwa, can you finish the dashboard UI by Friday?
    Marwa: Sure, I'll have it ready by end of day Thursday.
    Ahmed: Great. I'll handle the backend deployment to staging today.
    Sara: Should I write the test cases for the new endpoints?
    Ahmed: Yes Sara, please do that by tomorrow.
    Ahmed: Also, we need to update the documentation. Marwa, can you take that too?
    Marwa: No problem.
    """


@pytest.fixture
def sample_employees():
    class FakeEmployee:
        def __init__(self, id_, name, email):
            self.id = id_
            self.name = name
            self.email = email

    return [
        FakeEmployee("id-ahmed", "Ahmed Mohamed", "ahmed@test.com"),
        FakeEmployee("id-marwa", "Marwa Hassan", "marwa@test.com"),
        FakeEmployee("id-sara", "Sara Ali", "sara@test.com"),
    ]


# ── Unit tests: name normalization ────────────────────────────────────────────

def test_normalize_name_basic():
    from AI_services.app.utils.helpers import normalize_name
    assert normalize_name("Ahmed Mohamed") == "ahmed mohamed"
    assert normalize_name("  Marwa  ") == "marwa"


def test_names_match_exact():
    from AI_services.app.utils.helpers import names_match
    assert names_match("Ahmed", "ahmed") is True
    assert names_match("Marwa Hassan", "Marwa Hassan") is True


def test_names_match_partial():
    from AI_services.app.utils.helpers import names_match
    assert names_match("Ahmed", "Ahmed Mohamed") is True
    assert names_match("Sara", "Sara Ali") is True
    assert names_match("Ahmed", "Marwa") is False


def test_chunk_text_short():
    from AI_services.app.utils.helpers import chunk_text
    text = "Short text."
    chunks = chunk_text(text, max_chars=1000)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_long():
    from AI_services.app.utils.helpers import chunk_text
    text = ("This is a sentence. " * 500)
    chunks = chunk_text(text, max_chars=1000)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 1000 + 200


def test_parse_flexible_date():
    from AI_services.app.utils.helpers import parse_flexible_date
    assert parse_flexible_date("2025-01-17") == datetime(2025, 1, 17)
    assert parse_flexible_date("null") is None
    assert parse_flexible_date("") is None
    assert parse_flexible_date("17-01-2025") == datetime(2025, 1, 17)


# ── Unit tests: assignee resolution ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_resolve_assignee_exact_match(sample_employees):
    from AI_services.app.services.task_extraction_service import resolve_assignee

    db_mock = AsyncMock()
    emp_id, name = await resolve_assignee("Marwa", sample_employees, db_mock)
    assert emp_id == "id-marwa"
    assert name == "Marwa Hassan"


@pytest.mark.asyncio
async def test_resolve_assignee_full_name(sample_employees):
    from AI_services.app.services.task_extraction_service import resolve_assignee

    db_mock = AsyncMock()
    emp_id, name = await resolve_assignee("Ahmed Mohamed", sample_employees, db_mock)
    assert emp_id == "id-ahmed"


@pytest.mark.asyncio
async def test_resolve_assignee_no_match(sample_employees):
    from AI_services.app.services.task_extraction_service import resolve_assignee

    db_mock = AsyncMock()
    with patch("AI_services.app.services.task_extraction_service.chat_complete",
               new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = '{"matched_id": null, "matched_name": null, "confidence": 0.0}'
        emp_id, name = await resolve_assignee("John Smith", sample_employees, db_mock)
        assert emp_id is None


@pytest.mark.asyncio
async def test_resolve_assignee_empty_string(sample_employees):
    from AI_services.app.services.task_extraction_service import resolve_assignee

    db_mock = AsyncMock()
    emp_id, name = await resolve_assignee("", sample_employees, db_mock)
    assert emp_id is None
    assert name is None


# ── Unit tests: task extraction ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_task_extraction_parses_llm_output(sample_transcript, sample_employees):
    from AI_services.app.services.task_extraction_service import TaskExtractionService

    fake_llm_response = json.dumps({
        "tasks": [
            {
                "title": "Finish dashboard UI",
                "description": None,
                "assignee": "Marwa",
                "deadline": "2025-01-16",
                "priority": "HIGH",
                "category": "design",
                "estimated_hours": 8.0,
                "source_quote": "Marwa, can you finish the dashboard UI by Friday?",
            },
            {
                "title": "Deploy backend to staging",
                "description": None,
                "assignee": "Ahmed",
                "deadline": "2025-01-13",
                "priority": "HIGH",
                "category": "deployment",
                "estimated_hours": 2.0,
                "source_quote": "I'll handle the backend deployment to staging today.",
            },
            {
                "title": "Write test cases for new endpoints",
                "description": None,
                "assignee": "Sara",
                "deadline": "2025-01-14",
                "priority": "MEDIUM",
                "category": "testing",
                "estimated_hours": 4.0,
                "source_quote": "Sara, please do that by tomorrow.",
            },
        ]
    })

    db_mock = AsyncMock()
    db_mock.add = MagicMock()
    db_mock.flush = AsyncMock()

    meeting_mock = MagicMock()
    meeting_mock.id = "meeting-123"
    meeting_mock.title = "Sprint Planning"

    with patch("AI_services.app.services.task_extraction_service.chat_complete",
               new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = fake_llm_response

        service = TaskExtractionService()
        tasks = await service.extract_tasks(
            transcript=sample_transcript,
            meeting=meeting_mock,
            employees=sample_employees,
            db=db_mock,
        )

    assert len(tasks) == 3
    titles = [t.title for t in tasks]
    assert "Finish dashboard UI" in titles
    assert "Deploy backend to staging" in titles
    assert "Write test cases for new endpoints" in titles

    marwa_task = next(t for t in tasks if t.title == "Finish dashboard UI")
    assert marwa_task.assignee_id == "id-marwa"
    assert marwa_task.priority == "HIGH"

    ahmed_task = next(t for t in tasks if t.title == "Deploy backend to staging")
    assert ahmed_task.assignee_id == "id-ahmed"

    sara_task = next(t for t in tasks if t.title == "Write test cases for new endpoints")
    assert sara_task.assignee_id == "id-sara"


@pytest.mark.asyncio
async def test_task_extraction_empty_transcript(sample_employees):
    from AI_services.app.services.task_extraction_service import TaskExtractionService

    db_mock = AsyncMock()
    meeting_mock = MagicMock()
    meeting_mock.id = "meeting-456"

    service = TaskExtractionService()
    tasks = await service.extract_tasks(
        transcript="",
        meeting=meeting_mock,
        employees=sample_employees,
        db=db_mock,
    )
    assert tasks == []


@pytest.mark.asyncio
async def test_task_extraction_invalid_json(sample_transcript, sample_employees):
    from AI_services.app.services.task_extraction_service import TaskExtractionService

    db_mock = AsyncMock()
    db_mock.add = MagicMock()
    db_mock.flush = AsyncMock()
    meeting_mock = MagicMock()
    meeting_mock.id = "meeting-789"

    with patch("AI_services.app.services.task_extraction_service.chat_complete",
               new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "not valid json at all"

        service = TaskExtractionService()
        tasks = await service.extract_tasks(
            transcript=sample_transcript,
            meeting=meeting_mock,
            employees=sample_employees,
            db=db_mock,
        )
    assert tasks == []


# ── Unit tests: summarization ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_summarization_parses_correctly(sample_transcript, sample_employees):
    from AI_services.app.services.summarization_service import SummarizationService

    fake_summary = json.dumps({
        "overview": "The team held a sprint planning meeting.",
        "key_points": ["Dashboard UI due Thursday", "Backend deployment today"],
        "decisions": ["Use PostgreSQL for tasks"],
        "blockers": ["Waiting on design assets"],
        "next_steps": ["Ahmed deploys backend", "Marwa finishes dashboard"],
        "action_items": [{"task": "Deploy backend", "owner": "Ahmed", "deadline": "2025-01-13"}],
        "full_markdown": "# Sprint Planning\n\nThe team discussed Q2...",
    })

    db_mock = AsyncMock()
    db_mock.add = MagicMock()
    db_mock.flush = AsyncMock()
    meeting_mock = MagicMock()
    meeting_mock.id = "meeting-999"
    meeting_mock.title = "Sprint Planning"

    with patch("AI_services.app.services.summarization_service.chat_complete",
               new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = fake_summary

        service = SummarizationService()
        summary = await service.summarize(
            transcript=sample_transcript,
            meeting=meeting_mock,
            attendees=sample_employees,
            db=db_mock,
        )

    assert summary.overview == "The team held a sprint planning meeting."
    assert len(summary.key_points) == 2
    assert len(summary.decisions) == 1
    assert len(summary.next_steps) == 2
    assert summary.full_markdown.startswith("# Sprint Planning")


# ── Unit tests: WebSocket manager ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connection_manager_connect_disconnect():
    from AI_services.app.websocket.manager import ConnectionManager

    mgr = ConnectionManager()
    ws_mock = AsyncMock()
    ws_mock.send_text = AsyncMock()

    await mgr.connect(ws_mock, "meeting-1", "emp-1")
    assert mgr.connection_count("meeting-1") == 1
    assert mgr.meeting_has_connections("meeting-1")

    mgr.disconnect(ws_mock)
    assert mgr.connection_count("meeting-1") == 0
    assert not mgr.meeting_has_connections("meeting-1")


@pytest.mark.asyncio
async def test_broadcast_to_meeting_sends_to_all():
    from AI_services.app.websocket.manager import ConnectionManager

    mgr = ConnectionManager()
    ws1, ws2, ws3 = AsyncMock(), AsyncMock(), AsyncMock()

    await mgr.connect(ws1, "meeting-1", "emp-1")
    await mgr.connect(ws2, "meeting-1", "emp-2")
    await mgr.connect(ws3, "meeting-1", "emp-3")

    await mgr.broadcast_to_meeting("meeting-1", "test_event", {"msg": "hello"})

    assert ws1.send_text.called
    assert ws2.send_text.called
    assert ws3.send_text.called


@pytest.mark.asyncio
async def test_send_to_employee_targets_only_one():
    from AI_services.app.websocket.manager import ConnectionManager

    mgr = ConnectionManager()
    ws_ahmed = AsyncMock()
    ws_marwa = AsyncMock()

    await mgr.connect(ws_ahmed, "meeting-1", "emp-ahmed")
    await mgr.connect(ws_marwa, "meeting-1", "emp-marwa")

    await mgr.send_to_employee("emp-ahmed", "task_extracted", {"title": "Deploy backend"})

    assert ws_ahmed.send_text.called
    assert not ws_marwa.send_text.called


# ── Unit tests: translation ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_detect_language_arabic():
    from AI_services.app.realtime.translator import detect_language
    arabic_text = "أحمد قال إننا بحاجة إلى نشر الخادم"
    lang = await detect_language(arabic_text)
    assert lang == "ar"


@pytest.mark.asyncio
async def test_detect_language_english():
    from AI_services.app.realtime.translator import detect_language
    english_text = "Ahmed said we need to deploy the backend today"
    lang = await detect_language(english_text)
    assert lang == "en"


@pytest.mark.asyncio
async def test_translation_pipeline_segment():
    from AI_services.app.realtime.translator import TranslationPipeline

    with patch(
        "AI_services.app.realtime.translator.chat_complete",
        new_callable=AsyncMock,
    ) as mock_llm, patch(
        "AI_services.app.realtime.translator.append_to_list",
        new_callable=AsyncMock,
    ):
        mock_llm.return_value = "أحمد قال إننا بحاجة إلى النشر"
        pipeline = TranslationPipeline("meeting-test")
        result = await pipeline.process_segment("Ahmed said we need to deploy", "en")

    assert result["en"] == "Ahmed said we need to deploy"
    assert "ar" in result
    assert result["source_lang"] == "en"


# ── Integration test: full pipeline mock ──────────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_task_before_summary(sample_transcript, sample_employees):
    """
    Critical: tasks MUST be extracted and saved before summarization runs.
    """
    call_order = []

    from AI_services.app.pipelines.meeting_end_pipeline import MeetingEndPipeline

    async def fake_extract_tasks(transcript, meeting, employees, db):
        call_order.append("task_extraction")
        task = MagicMock()
        task.id = "task-1"
        task.title = "Deploy backend"
        task.assignee_id = "id-ahmed"
        task.description = None
        task.priority = "HIGH"
        task.status = "TODO"
        task.deadline = None
        task.estimated_hours = None
        task.category = "deployment"
        task.source_quote = None
        return [task]

    async def fake_summarize(transcript, meeting, attendees, db):
        call_order.append("summarization")
        summary = MagicMock()
        summary.id = "summary-1"
        summary.overview = "Test overview"
        summary.key_points = []
        summary.decisions = []
        summary.blockers = []
        summary.next_steps = []
        summary.action_items = []
        return summary

    with patch("AI_services.app.pipelines.meeting_end_pipeline.task_extraction_service.extract_tasks",
               side_effect=fake_extract_tasks), \
         patch("AI_services.app.pipelines.meeting_end_pipeline.summarization_service.summarize",
               side_effect=fake_summarize), \
         patch("AI_services.app.pipelines.meeting_end_pipeline.get_list",
               new_callable=AsyncMock, return_value=[{"text": "test"}]), \
         patch("AI_services.app.pipelines.meeting_end_pipeline.get_value",
               new_callable=AsyncMock, return_value=sample_transcript), \
         patch("AI_services.app.pipelines.meeting_end_pipeline.manager") as mock_manager:

        mock_manager.send_to_employee = AsyncMock()
        mock_manager.broadcast_to_meeting = AsyncMock()

        db_mock = AsyncMock()
        db_mock.execute = AsyncMock()
        db_mock.add = MagicMock()
        db_mock.flush = AsyncMock()
        db_mock.commit = AsyncMock()

        meeting_mock = MagicMock()
        meeting_mock.id = "meeting-999"
        meeting_mock.title = "Test Meeting"
        meeting_mock.attendees = sample_employees
        meeting_mock.host_id = "id-ahmed"

        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = meeting_mock
        db_mock.execute.return_value = scalar_mock

        translator_mock = MagicMock()
        translator_mock.translate_full_transcript = AsyncMock(return_value="ترجمة عربية")

        with patch("AI_services.app.pipelines.meeting_end_pipeline.TranslationPipeline",
                   return_value=translator_mock):
            pipeline = MeetingEndPipeline()
            await pipeline.run("meeting-999", db_mock)

    assert call_order.index("task_extraction") < call_order.index("summarization"), \
        "Task extraction MUST happen before summarization!"
    print(f"\n✓ Call order verified: {call_order}")
