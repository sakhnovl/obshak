import pytest
import pytest_asyncio
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch

from database.db import db
from src.ai import GeminiAI
from src.main import AdminFilter, Message, handle_message, is_rate_limited


class MockGeminiAI:
    def format_history(self, db_history):
        return [{"role": m["role"], "parts": [m["content"]]} for m in db_history]

    async def get_response(self, user_id, current_message, history):
        return "Mocked AI response"


@pytest_asyncio.fixture
async def setup_db():
    db.pool = None
    await db.connect()
    async with db.pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM messages")
            await cur.execute("DELETE FROM users")
    yield db
    await db.disconnect()


@pytest.mark.asyncio
async def test_context_isolation(setup_db):
    user1 = 12345
    user2 = 67890

    await setup_db.save_message(user1, "user1", "Name1", "user", "Hello from 1")
    await setup_db.save_message(user2, "user2", "Name2", "user", "Hello from 2")

    ctx1 = await setup_db.get_user_context(user1)
    ctx2 = await setup_db.get_user_context(user2)

    assert len(ctx1) == 1
    assert ctx1[0]["content"] == "Hello from 1"
    assert len(ctx2) == 1
    assert ctx2[0]["content"] == "Hello from 2"


@pytest.mark.asyncio
async def test_context_window(setup_db):
    user_id = 11111
    for i in range(25):
        await setup_db.save_message(user_id, "test", "test", "user", f"msg {i}")

    ctx = await setup_db.get_user_context(user_id, limit=20)
    assert len(ctx) == 20
    assert ctx[0]["content"] == "msg 5"
    assert ctx[-1]["content"] == "msg 24"


def test_ai_history_formatting():
    agent = GeminiAI.__new__(GeminiAI)
    db_history = [
        {"role": "user", "content": "Hi"},
        {"role": "model", "content": "Hello!"},
    ]

    formatted = agent.format_history(db_history)

    assert len(formatted) == 2
    assert formatted[0].role == "user"
    assert formatted[0].parts[0].text == "Hi"
    assert formatted[1].role == "model"
    assert formatted[1].parts[0].text == "Hello!"


def test_ai_sanitizes_reasoning_response():
    agent = GeminiAI.__new__(GeminiAI)
    raw_response = """
*   Question: "how are you?"
    *   Constraint 1: One short phrase.
    *   Constraint 2: In Russian.

    *   "All good, thanks!"

    All good, thanks!
""".strip()

    cleaned = agent.sanitize_response(raw_response)

    assert cleaned == "All good, thanks!"


def test_ai_generation_config_disables_afc():
    agent = GeminiAI.__new__(GeminiAI)

    config = agent.build_generation_config()

    assert config.automatic_function_calling is not None
    assert config.automatic_function_calling.disable is True


@pytest.mark.asyncio
async def test_ai_falls_back_to_next_model_on_error():
    agent = GeminiAI.__new__(GeminiAI)
    agent._initialized = True
    agent.model_names = ["primary-model", "backup-model"]
    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    agent.clients = [mock_client]

    async def generate_content(model, contents, config):
        assert model in {"primary-model", "backup-model"}
        assert contents[-1].parts[0].text.endswith("User message:\nhello")
        assert config.automatic_function_calling is not None
        assert config.automatic_function_calling.disable is True
        if model == "primary-model":
            raise RuntimeError("primary model failed")
        return MagicMock(text="backup-model:hello")

    mock_client.aio.models.generate_content = AsyncMock(side_effect=generate_content)

    response = await agent.get_response(1, "hello", [])

    assert response == "backup-model:hello"


@pytest.mark.asyncio
async def test_ai_raises_when_all_models_fail():
    agent = GeminiAI.__new__(GeminiAI)
    agent._initialized = True
    agent.model_names = ["primary-model", "backup-model"]
    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    agent.clients = [mock_client]

    async def generate_content(model, contents, config):
        assert contents[-1].parts[0].text.endswith("User message:\nhello")
        assert config.automatic_function_calling is not None
        assert config.automatic_function_calling.disable is True
        raise RuntimeError("failed:hello")

    mock_client.aio.models.generate_content = AsyncMock(side_effect=generate_content)

    with pytest.raises(RuntimeError, match="failed:hello"):
        await agent.get_response(1, "hello", [])


@pytest.mark.asyncio
async def test_admin_filter():
    with patch("src.main.ADMIN_IDS", [999]):
        admin_filter = AdminFilter()

        msg_admin = MagicMock(spec=Message)
        msg_admin.from_user = MagicMock()
        msg_admin.from_user.id = 999

        msg_user = MagicMock(spec=Message)
        msg_user.from_user = MagicMock()
        msg_user.from_user.id = 111

        assert await admin_filter(msg_admin) is True
        assert await admin_filter(msg_user) is False


@pytest.mark.asyncio
async def test_admin_commands_logic(setup_db):
    user_id = 22222
    await setup_db.save_message(user_id, "test", "test", "user", "msg")

    count = await setup_db.clear_user_context(user_id)
    assert count == 1

    ctx = await setup_db.get_user_context(user_id)
    assert len(ctx) == 0


def test_user_is_not_rate_limited_within_five_requests():
    request_times = deque([0.0, 10.0, 20.0, 30.0])

    result = is_rate_limited(request_times, current_time=40.0)

    assert result is False
    assert list(request_times) == [0.0, 10.0, 20.0, 30.0, 40.0]


def test_user_is_rate_limited_on_sixth_request_within_minute():
    request_times = deque([0.0, 5.0, 10.0, 15.0, 20.0])

    result = is_rate_limited(request_times, current_time=25.0)

    assert result is True
    assert list(request_times) == [0.0, 5.0, 10.0, 15.0, 20.0]


def test_rate_limit_discards_requests_older_than_one_minute():
    request_times = deque([0.0, 5.0, 10.0, 15.0, 20.0])

    result = is_rate_limited(request_times, current_time=75.0)

    assert result is False
    assert list(request_times) == [20.0, 75.0]


@pytest.mark.asyncio
async def test_handle_message_replies_to_original_message():
    user = MagicMock()
    user.id = 123
    user.username = "tester"
    user.first_name = "Test"

    message = MagicMock(spec=Message)
    message.from_user = user
    message.text = "hello"
    message.reply = AsyncMock()
    message.answer = AsyncMock()

    with patch("src.main.is_rate_limited", return_value=False), patch(
        "src.main.db.get_user_context", new=AsyncMock(return_value=[])
    ), patch("src.main.db.save_message", new=AsyncMock()), patch(
        "src.main.ai_agent.get_response", new=AsyncMock(return_value="reply text")
    ):
        await handle_message(message)

    message.reply.assert_awaited_once_with("reply text")
    message.answer.assert_not_called()
