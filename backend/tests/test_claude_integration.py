"""
Live integration tests for ClaudeService.
These tests make real API calls and require a valid ANTHROPIC_API_KEY.

Run with: ANTHROPIC_API_KEY=sk-ant-... pytest tests/test_claude_integration.py -v -s
Skip automatically if no API key is set.
"""
import json
import os
import sys
import tempfile

import pytest

# Add backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Skip all tests if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set -- skipping live integration tests",
)


@pytest.fixture(scope="module")
def service():
    """Initialize ClaudeService with real API key for integration tests."""
    # Set required env vars for Settings
    os.environ.setdefault("ANTHROPIC_MODEL", "claude-opus-4-6")
    os.environ.setdefault("ANTHROPIC_TEMPERATURE", "0.5")
    os.environ.setdefault("ANTHROPIC_TIMEOUT", "120")
    os.environ.setdefault("ANTHROPIC_MAX_TOKENS", "128000")
    os.environ.setdefault("LLM_PROVIDER", "claude")
    os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
    os.environ.setdefault("AUTH0_DOMAIN", "test")
    os.environ.setdefault("AUTH0_CLIENT_ID", "test")
    os.environ.setdefault("AUTH0_CLIENT_SECRET", "test")
    os.environ.setdefault("AUTH0_AUDIENCE", "test")
    os.environ.setdefault("AUTH0_MANAGEMENT_API_AUDIENCE", "test")
    os.environ.setdefault("AUTH0_MANAGEMENT_CLIENT_ID", "test")
    os.environ.setdefault("AUTH0_MANAGEMENT_CLIENT_SECRET", "test")
    os.environ.setdefault("SECRET_KEY", "test-secret-key")

    from app.services.claude_service import ClaudeService

    ClaudeService.initialize_client()
    return ClaudeService()


# ==================== BASIC COMPLETION ====================


class TestLiveCompletion:

    @pytest.mark.asyncio
    async def test_basic_message(self, service):
        """Send a basic message and verify response structure."""
        result = await service.generate_completion(
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Respond briefly."},
                {"role": "user", "content": "Say 'hello world' and nothing else."},
            ],
            max_output_tokens=100,
        )

        assert result["content"], "Response content should not be empty"
        assert result["tokens_used"] > 0, "Token count should be positive"
        assert result["prompt_tokens"] > 0
        assert result["completion_tokens"] > 0
        assert result["finish_reason"] in ("end_turn", "max_tokens", "stop_sequence")
        assert result["response_id"] is not None
        print(f"  Response: {result['content'][:100]}")
        print(f"  Tokens: {result['tokens_used']} (in={result['prompt_tokens']}, out={result['completion_tokens']})")

    @pytest.mark.asyncio
    async def test_developer_role_works(self, service):
        """Developer role (OpenAI convention) should work via system extraction."""
        result = await service.generate_completion(
            messages=[
                {"role": "developer", "content": "Always respond with exactly one word."},
                {"role": "user", "content": "What color is the sky?"},
            ],
            max_output_tokens=50,
        )

        assert result["content"], "Response should not be empty"
        # Should be a very short response
        assert len(result["content"].split()) <= 5
        print(f"  Response: {result['content']}")


# ==================== JSON COMPLETION ====================


class TestLiveJsonCompletion:

    @pytest.mark.asyncio
    async def test_json_output(self, service):
        """JSON mode should return valid parseable JSON."""
        result = await service.generate_json_completion(
            messages=[
                {"role": "system", "content": "You extract structured data."},
                {"role": "user", "content": 'Extract: Name is John, age is 30, city is London. Return as JSON with keys: name, age, city.'},
            ],
            max_output_tokens=200,
        )

        assert "parsed_content" in result, "Should have parsed_content key"
        parsed = result["parsed_content"]
        assert isinstance(parsed, dict), "Parsed content should be a dict"
        print(f"  Parsed JSON: {json.dumps(parsed, indent=2)}")

        # Verify extracted fields
        assert "name" in parsed or "Name" in parsed
        assert "age" in parsed or "Age" in parsed


# ==================== EXTENDED THINKING ====================


class TestLiveThinking:

    @pytest.mark.asyncio
    async def test_medium_reasoning(self, service):
        """Medium reasoning should work with extended thinking."""
        result = await service.generate_completion(
            messages=[
                {"role": "user", "content": "What is 15 * 17? Just give the number."},
            ],
            reasoning_effort="medium",
            max_output_tokens=200,
        )

        assert result["content"], "Response should not be empty"
        assert "255" in result["content"], f"Expected 255 in response, got: {result['content']}"
        print(f"  Response: {result['content']}")
        print(f"  Tokens: {result['tokens_used']}")


# ==================== FILE UPLOAD ====================


class TestLiveFileUpload:

    @pytest.mark.asyncio
    async def test_upload_text_file(self, service):
        """Upload a text file and verify response."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("This is a test document.\nIt has multiple lines.\n")
            temp_path = f.name

        try:
            result = await service.upload_file(temp_path)

            assert result is not None, "Upload should succeed"
            assert result["id"], "Should have a file ID"
            assert result["filename"].endswith(".txt")
            assert result["bytes"] > 0
            print(f"  Uploaded file ID: {result['id']}")
            print(f"  Filename: {result['filename']}, Size: {result['bytes']} bytes")
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_upload_and_reference_in_message(self, service):
        """Upload a file and reference it in a completion."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Company: Acme Corp\nRevenue: $5M\nEmployees: 50\nFounded: 2010\n")
            temp_path = f.name

        try:
            # Upload file
            upload_result = await service.upload_file(temp_path)
            assert upload_result is not None

            file_id = upload_result["id"]

            # Use file in completion
            result = await service.generate_completion(
                messages=[
                    {"role": "system", "content": "You extract data from documents."},
                    {"role": "user", "content": "What company is described in the attached file? Just name the company."},
                ],
                file_ids=[file_id],
                max_output_tokens=100,
            )

            assert result["content"], "Response should not be empty"
            assert "acme" in result["content"].lower(), f"Expected 'Acme' in response: {result['content']}"
            print(f"  Response: {result['content']}")
        finally:
            os.unlink(temp_path)


# ==================== SPECIALIZED METHODS ====================


class TestLiveSpecializedMethods:

    @pytest.mark.asyncio
    async def test_generate_summary(self, service):
        """Test generate_summary method."""
        result = await service.generate_summary(
            system_prompt="Summarize the following user responses in 2-3 sentences.",
            user_responses={
                "q1_business_name": "Acme Corp",
                "q2_industry": "Technology",
                "q3_employees": "50",
                "q4_biggest_challenge": "Scaling operations while maintaining quality",
            },
            reasoning_effort="low",
        )

        assert result["content"], "Summary should not be empty"
        assert len(result["content"]) > 20, "Summary should be meaningful"
        print(f"  Summary: {result['content'][:200]}")

    @pytest.mark.asyncio
    async def test_generate_tasks(self, service):
        """Test generate_tasks method returns valid task JSON."""
        result = await service.generate_tasks(
            task_prompt="Generate 2-3 practical tasks.",
            diagnostic_summary="Acme Corp is a small tech company with gaps in financial planning and HR.",
            json_extract={
                "q_financial_plan": "No formal budget or financial forecasting in place",
                "q_hr_handbook": "No employee handbook exists",
            },
            roadmap=[
                {"module": "M3 Financial", "score": 2.1, "rag": "Red", "rank": 1},
                {"module": "M5 Human Resources", "score": 2.8, "rag": "Amber", "rank": 2},
            ],
            reasoning_effort="low",
        )

        assert "parsed_content" in result, "Should have parsed JSON"
        parsed = result["parsed_content"]
        assert "tasks" in parsed, f"Should have 'tasks' key, got: {list(parsed.keys())}"
        assert len(parsed["tasks"]) >= 1, "Should have at least 1 task"
        print(f"  Generated {len(parsed['tasks'])} tasks")
        for t in parsed["tasks"]:
            print(f"    - {t.get('title', 'untitled')}")
