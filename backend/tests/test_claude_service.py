"""
Unit tests for ClaudeService.
Tests message conversion, response mapping, and interface compatibility.

Run with: pytest tests/test_claude_service.py -v
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os

# Add backend directory to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ==================== FIXTURES ====================


@pytest.fixture
def claude_service():
    """Create a ClaudeService instance with a mocked client."""
    with patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "sk-ant-test-key",
        "ANTHROPIC_MODEL": "claude-opus-4-6",
        "ANTHROPIC_TEMPERATURE": "0.5",
        "ANTHROPIC_TIMEOUT": "600",
        "ANTHROPIC_MAX_TOKENS": "128000",
        "LLM_PROVIDER": "claude",
        "DATABASE_URL": "sqlite:///test.db",
        "AUTH0_DOMAIN": "test",
        "AUTH0_CLIENT_ID": "test",
        "AUTH0_CLIENT_SECRET": "test",
        "AUTH0_AUDIENCE": "test",
        "AUTH0_MANAGEMENT_API_AUDIENCE": "test",
        "AUTH0_MANAGEMENT_CLIENT_ID": "test",
        "AUTH0_MANAGEMENT_CLIENT_SECRET": "test",
        "SECRET_KEY": "test-secret-key",
    }):
        from app.services.claude_service import ClaudeService
        service = ClaudeService()
        # Mock the client
        service.__class__._client = MagicMock()
        return service


@pytest.fixture
def mock_response():
    """Create a mock Claude API response."""
    response = MagicMock()
    response.id = "msg_test123"
    response.model = "claude-opus-4-6"
    response.stop_reason = "end_turn"

    # Create content blocks
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Hello, this is a test response."
    response.content = [text_block]

    # Usage
    response.usage = MagicMock()
    response.usage.input_tokens = 100
    response.usage.output_tokens = 50

    return response


@pytest.fixture
def mock_json_response():
    """Create a mock Claude API response with JSON content."""
    response = MagicMock()
    response.id = "msg_json123"
    response.model = "claude-opus-4-6"
    response.stop_reason = "end_turn"

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = '{"key": "value", "count": 42}'
    response.content = [text_block]

    response.usage = MagicMock()
    response.usage.input_tokens = 200
    response.usage.output_tokens = 80

    return response


@pytest.fixture
def mock_thinking_response():
    """Create a mock response with thinking blocks."""
    response = MagicMock()
    response.id = "msg_think123"
    response.model = "claude-opus-4-6"
    response.stop_reason = "end_turn"

    # Thinking block (should be skipped)
    thinking_block = MagicMock()
    thinking_block.type = "thinking"
    thinking_block.text = "Let me think about this..."

    # Text block (should be extracted)
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Here is my answer."

    response.content = [thinking_block, text_block]

    response.usage = MagicMock()
    response.usage.input_tokens = 150
    response.usage.output_tokens = 100

    return response


# ==================== MESSAGE CONVERSION TESTS ====================


class TestMessageConversion:
    """Test _convert_messages_to_claude_format()"""

    def test_system_message_extraction(self, claude_service):
        """System messages should be extracted to the system parameter."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]

        system_prompt, claude_messages = claude_service._convert_messages_to_claude_format(messages)

        assert system_prompt == "You are a helpful assistant."
        assert len(claude_messages) == 1
        assert claude_messages[0]["role"] == "user"
        assert claude_messages[0]["content"] == "Hello"

    def test_developer_role_extraction(self, claude_service):
        """Developer role (OpenAI convention) should also be extracted as system."""
        messages = [
            {"role": "developer", "content": "System instructions here."},
            {"role": "user", "content": "What's up?"},
        ]

        system_prompt, claude_messages = claude_service._convert_messages_to_claude_format(messages)

        assert system_prompt == "System instructions here."
        assert len(claude_messages) == 1

    def test_multiple_system_messages_concatenated(self, claude_service):
        """Multiple system messages should be concatenated."""
        messages = [
            {"role": "system", "content": "Part 1 of instructions."},
            {"role": "system", "content": "Part 2 of instructions."},
            {"role": "user", "content": "Go"},
        ]

        system_prompt, claude_messages = claude_service._convert_messages_to_claude_format(messages)

        assert "Part 1" in system_prompt
        assert "Part 2" in system_prompt
        assert len(claude_messages) == 1

    def test_no_system_message(self, claude_service):
        """No system message should result in empty system prompt."""
        messages = [
            {"role": "user", "content": "Hello"},
        ]

        system_prompt, claude_messages = claude_service._convert_messages_to_claude_format(messages)

        assert system_prompt == ""
        assert len(claude_messages) == 1

    def test_multi_turn_conversation(self, claude_service):
        """Multi-turn conversations should preserve user/assistant ordering."""
        messages = [
            {"role": "system", "content": "Be helpful."},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
            {"role": "user", "content": "How are you?"},
        ]

        system_prompt, claude_messages = claude_service._convert_messages_to_claude_format(messages)

        assert system_prompt == "Be helpful."
        assert len(claude_messages) == 3
        assert claude_messages[0]["role"] == "user"
        assert claude_messages[1]["role"] == "assistant"
        assert claude_messages[2]["role"] == "user"

    def test_file_ids_as_document_blocks(self, claude_service):
        """File IDs should be attached as document blocks to the last user message."""
        messages = [
            {"role": "user", "content": "Analyze this file"},
        ]

        system_prompt, claude_messages = claude_service._convert_messages_to_claude_format(
            messages, file_ids=["file_abc123"]
        )

        content = claude_messages[0]["content"]
        assert isinstance(content, list)

        # Find document block
        doc_blocks = [b for b in content if b.get("type") == "document"]
        assert len(doc_blocks) == 1
        assert doc_blocks[0]["source"]["type"] == "file"
        assert doc_blocks[0]["source"]["file_id"] == "file_abc123"

        # Find text block
        text_blocks = [b for b in content if b.get("type") == "text"]
        assert len(text_blocks) == 1
        assert text_blocks[0]["text"] == "Analyze this file"

    def test_ci_file_ids_as_container_upload_blocks(self, claude_service):
        """CI file IDs should be attached as container_upload blocks."""
        messages = [
            {"role": "user", "content": "Analyze this data"},
        ]

        system_prompt, claude_messages = claude_service._convert_messages_to_claude_format(
            messages, ci_file_ids=["file_csv123"]
        )

        content = claude_messages[0]["content"]
        assert isinstance(content, list)

        # Find container_upload block
        cu_blocks = [b for b in content if b.get("type") == "container_upload"]
        assert len(cu_blocks) == 1
        assert cu_blocks[0]["file_id"] == "file_csv123"

    def test_mixed_file_ids(self, claude_service):
        """Both document and container_upload blocks should coexist."""
        messages = [
            {"role": "user", "content": "Analyze"},
        ]

        system_prompt, claude_messages = claude_service._convert_messages_to_claude_format(
            messages,
            file_ids=["file_pdf1"],
            ci_file_ids=["file_csv1"],
        )

        content = claude_messages[0]["content"]
        doc_blocks = [b for b in content if b.get("type") == "document"]
        cu_blocks = [b for b in content if b.get("type") == "container_upload"]
        text_blocks = [b for b in content if b.get("type") == "text"]

        assert len(doc_blocks) == 1
        assert len(cu_blocks) == 1
        assert len(text_blocks) == 1


# ==================== COMPLETION TESTS ====================


class TestGenerateCompletion:
    """Test generate_completion() response mapping."""

    @pytest.mark.asyncio
    async def test_basic_completion(self, claude_service, mock_response):
        """Basic completion should return correct dict shape."""
        claude_service.client.beta.messages.create = AsyncMock(return_value=mock_response)

        result = await claude_service.generate_completion(
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert "content" in result
        assert "model" in result
        assert "tokens_used" in result
        assert "prompt_tokens" in result
        assert "completion_tokens" in result
        assert "finish_reason" in result
        assert "response_id" in result
        assert "output_summary" in result

    @pytest.mark.asyncio
    async def test_response_values(self, claude_service, mock_response):
        """Response values should be correctly mapped."""
        claude_service.client.beta.messages.create = AsyncMock(return_value=mock_response)

        result = await claude_service.generate_completion(
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert result["content"] == "Hello, this is a test response."
        assert result["tokens_used"] == 150  # 100 + 50
        assert result["prompt_tokens"] == 100
        assert result["completion_tokens"] == 50
        assert result["finish_reason"] == "end_turn"
        assert result["response_id"] == "msg_test123"

    @pytest.mark.asyncio
    async def test_thinking_response_skips_thinking_blocks(self, claude_service, mock_thinking_response):
        """When thinking is enabled, thinking blocks should be skipped."""
        claude_service.client.beta.messages.create = AsyncMock(return_value=mock_thinking_response)

        result = await claude_service.generate_completion(
            messages=[{"role": "user", "content": "Think about this"}],
            reasoning_effort="medium",
        )

        # Should get the text block, not the thinking block
        assert result["content"] == "Here is my answer."

    @pytest.mark.asyncio
    async def test_code_interpreter_tool_mapping(self, claude_service, mock_response):
        """code_interpreter tools should be mapped to code_execution_20250825."""
        claude_service.client.beta.messages.create = AsyncMock(return_value=mock_response)

        await claude_service.generate_completion(
            messages=[{"role": "user", "content": "Analyze"}],
            tools=[{
                "type": "code_interpreter",
                "container": {"type": "auto", "file_ids": ["file_csv1"]},
            }],
        )

        # Verify the API was called with correct tool type
        call_kwargs = claude_service.client.beta.messages.create.call_args[1]
        tools = call_kwargs.get("tools", [])
        assert len(tools) == 1
        assert tools[0]["type"] == "code_execution_20250825"
        assert tools[0]["name"] == "code_execution"

        # Verify file_ids are in messages as container_upload
        messages = call_kwargs.get("messages", [])
        last_msg = messages[-1]
        content = last_msg["content"]
        cu_blocks = [b for b in content if isinstance(b, dict) and b.get("type") == "container_upload"]
        assert len(cu_blocks) == 1
        assert cu_blocks[0]["file_id"] == "file_csv1"

    @pytest.mark.asyncio
    async def test_json_mode_adds_instruction(self, claude_service, mock_response):
        """json_mode should append JSON instruction to system prompt."""
        claude_service.client.beta.messages.create = AsyncMock(return_value=mock_response)

        await claude_service.generate_completion(
            messages=[
                {"role": "system", "content": "Be helpful."},
                {"role": "user", "content": "Give me JSON"},
            ],
            json_mode=True,
        )

        call_kwargs = claude_service.client.beta.messages.create.call_args[1]
        system = call_kwargs.get("system", "")
        assert "valid JSON only" in system
        assert "Be helpful" in system

    @pytest.mark.asyncio
    async def test_reasoning_effort_medium(self, claude_service, mock_response):
        """Medium reasoning effort should enable thinking with budget_tokens."""
        claude_service.client.beta.messages.create = AsyncMock(return_value=mock_response)

        await claude_service.generate_completion(
            messages=[{"role": "user", "content": "Think"}],
            reasoning_effort="medium",
        )

        call_kwargs = claude_service.client.beta.messages.create.call_args[1]
        thinking = call_kwargs.get("thinking", {})
        assert thinking["type"] == "enabled"
        assert thinking["budget_tokens"] == 10000
        # Temperature must be 1.0 when thinking is enabled
        assert call_kwargs.get("temperature") == 1.0

    @pytest.mark.asyncio
    async def test_reasoning_effort_high(self, claude_service, mock_response):
        """High reasoning effort should use higher budget_tokens."""
        claude_service.client.beta.messages.create = AsyncMock(return_value=mock_response)

        await claude_service.generate_completion(
            messages=[{"role": "user", "content": "Think hard"}],
            reasoning_effort="high",
        )

        call_kwargs = claude_service.client.beta.messages.create.call_args[1]
        thinking = call_kwargs.get("thinking", {})
        assert thinking["budget_tokens"] == 32000

    @pytest.mark.asyncio
    async def test_reasoning_effort_low_no_thinking(self, claude_service, mock_response):
        """Low reasoning effort should not enable thinking."""
        claude_service.client.beta.messages.create = AsyncMock(return_value=mock_response)

        await claude_service.generate_completion(
            messages=[{"role": "user", "content": "Quick answer"}],
            reasoning_effort="low",
        )

        call_kwargs = claude_service.client.beta.messages.create.call_args[1]
        assert "thinking" not in call_kwargs

    @pytest.mark.asyncio
    async def test_beta_header_included(self, claude_service, mock_response):
        """Files API beta header should always be included."""
        claude_service.client.beta.messages.create = AsyncMock(return_value=mock_response)

        await claude_service.generate_completion(
            messages=[{"role": "user", "content": "Hello"}],
        )

        call_kwargs = claude_service.client.beta.messages.create.call_args[1]
        assert "files-api-2025-04-14" in call_kwargs.get("betas", [])


# ==================== JSON COMPLETION TESTS ====================


class TestGenerateJsonCompletion:
    """Test generate_json_completion() JSON parsing."""

    @pytest.mark.asyncio
    async def test_direct_json_parse(self, claude_service, mock_json_response):
        """Valid JSON should be parsed directly."""
        claude_service.client.beta.messages.create = AsyncMock(return_value=mock_json_response)

        result = await claude_service.generate_json_completion(
            messages=[{"role": "user", "content": "Give JSON"}],
        )

        assert "parsed_content" in result
        assert result["parsed_content"]["key"] == "value"
        assert result["parsed_content"]["count"] == 42

    @pytest.mark.asyncio
    async def test_json_from_markdown_block(self, claude_service):
        """JSON wrapped in markdown should be extracted."""
        response = MagicMock()
        response.id = "msg_md123"
        response.model = "claude-opus-4-6"
        response.stop_reason = "end_turn"

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = '```json\n{"result": "success"}\n```'
        response.content = [text_block]
        response.usage = MagicMock()
        response.usage.input_tokens = 50
        response.usage.output_tokens = 30

        claude_service.client.beta.messages.create = AsyncMock(return_value=response)

        result = await claude_service.generate_json_completion(
            messages=[{"role": "user", "content": "Give JSON"}],
        )

        assert result["parsed_content"]["result"] == "success"


# ==================== JSON REPAIR TESTS ====================


class TestRepairJson:
    """Test _repair_json() helper."""

    def test_remove_trailing_comma(self, claude_service):
        content = '{"a": 1, "b": 2,}'
        repaired = claude_service._repair_json(content)
        parsed = json.loads(repaired)
        assert parsed == {"a": 1, "b": 2}

    def test_add_missing_comma_between_objects(self, claude_service):
        content = '[{"a": 1}{"b": 2}]'
        repaired = claude_service._repair_json(content)
        parsed = json.loads(repaired)
        assert len(parsed) == 2

    def test_strip_markdown_json_block(self, claude_service):
        content = '```json\n{"key": "val"}\n```'
        repaired = claude_service._repair_json(content)
        parsed = json.loads(repaired)
        assert parsed["key"] == "val"


# ==================== UPLOAD FILE TESTS ====================


class TestUploadFile:
    """Test upload_file() method."""

    @pytest.mark.asyncio
    async def test_upload_file_success(self, claude_service, tmp_path):
        """Successful file upload should return correct dict shape."""
        # Create a test file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"%PDF-1.4 test content")

        mock_upload_response = MagicMock()
        mock_upload_response.id = "file_test123"
        mock_upload_response.created_at = "2026-03-18T00:00:00Z"

        claude_service.client.beta.files.upload = AsyncMock(return_value=mock_upload_response)

        result = await claude_service.upload_file(str(test_file))

        assert result is not None
        assert result["id"] == "file_test123"
        assert result["filename"] == "test.pdf"
        assert result["bytes"] > 0
        assert result["purpose"] == "user_data"

    @pytest.mark.asyncio
    async def test_upload_file_not_found(self, claude_service):
        """Missing file should return None."""
        result = await claude_service.upload_file("/nonexistent/file.pdf")
        assert result is None

    @pytest.mark.asyncio
    async def test_upload_file_api_error(self, claude_service, tmp_path):
        """API error during upload should return None."""
        test_file = tmp_path / "test.csv"
        test_file.write_text("a,b,c\n1,2,3")

        claude_service.client.beta.files.upload = AsyncMock(side_effect=Exception("Upload failed"))

        result = await claude_service.upload_file(str(test_file))
        assert result is None


# ==================== MIME TYPE TESTS ====================


class TestMimeType:
    """Test _get_mime_type() helper."""

    def test_pdf_mime(self, claude_service):
        assert claude_service._get_mime_type("doc.pdf") == "application/pdf"

    def test_csv_mime(self, claude_service):
        assert claude_service._get_mime_type("data.csv") == "text/csv"

    def test_xlsx_mime(self, claude_service):
        mime = claude_service._get_mime_type("report.xlsx")
        assert "spreadsheet" in mime or "excel" in mime.lower() or "officedocument" in mime

    def test_png_mime(self, claude_service):
        assert claude_service._get_mime_type("image.png") == "image/png"

    def test_unknown_extension(self, claude_service):
        assert claude_service._get_mime_type("file.xyz") == "application/octet-stream"


# ==================== RETURN FORMAT COMPATIBILITY ====================


class TestReturnFormatCompatibility:
    """Ensure return format matches OpenAI service for drop-in replacement."""

    EXPECTED_KEYS = {
        "content", "model", "tokens_used", "prompt_tokens",
        "completion_tokens", "finish_reason", "response_id", "output_summary",
    }

    @pytest.mark.asyncio
    async def test_generate_completion_keys(self, claude_service, mock_response):
        claude_service.client.beta.messages.create = AsyncMock(return_value=mock_response)

        result = await claude_service.generate_completion(
            messages=[{"role": "user", "content": "test"}],
        )

        assert set(result.keys()) == self.EXPECTED_KEYS

    @pytest.mark.asyncio
    async def test_generate_json_completion_keys(self, claude_service, mock_json_response):
        claude_service.client.beta.messages.create = AsyncMock(return_value=mock_json_response)

        result = await claude_service.generate_json_completion(
            messages=[{"role": "user", "content": "test"}],
        )

        expected = self.EXPECTED_KEYS | {"parsed_content"}
        assert expected.issubset(set(result.keys()))
