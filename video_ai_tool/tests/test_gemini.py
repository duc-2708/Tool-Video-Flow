# file: tests/test_gemini.py
"""Mock Gemini; không gửi request hoặc sử dụng key thật."""
from pathlib import Path
from unittest.mock import Mock
import pytest
from pydantic import SecretStr, ValidationError
from google.genai import errors
from config.settings import Settings
from providers.llm_base import ProviderError
from providers.llm_gemini import GeminiProvider, transient_gemini
from schemas.research_brief import ResearchBrief
from providers.llm_gemini import GeminiOutputError
from providers.research_payload import ResearchFactsResponse


def test_sdk_structured_output_timeout_and_close(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = Mock()
    client.models.generate_content.return_value.text = "{}"
    constructor = Mock(return_value=client)
    monkeypatch.setattr("providers.llm_gemini.genai.Client", constructor)
    settings = Settings(root_dir=tmp_path, gemini_api_key=SecretStr("fixture-only"), gemini_model="fixture-model",
                        request_timeout_sec=12,gemini_timeout_sec=14)
    provider = GeminiProvider(settings)
    assert provider.generate_json("fixture prompt", ResearchBrief) == "{}"
    options = constructor.call_args.kwargs["http_options"]
    assert options.timeout == 14000 and options.retry_options.attempts == 1
    config = client.models.generate_content.call_args.kwargs["config"]
    assert config.response_schema is None and config.response_mime_type == "application/json"
    assert config.response_json_schema == ResearchFactsResponse.model_json_schema()
    provider.close()
    client.close.assert_called_once()


def test_provider_error_does_not_expose_http_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = Mock()
    client.models.generate_content.side_effect = errors.ClientError(403, {"error": {"message": "fixture-private-marker", "code": 403}})
    monkeypatch.setattr("providers.llm_gemini.genai.Client", Mock(return_value=client))
    provider = GeminiProvider(Settings(root_dir=tmp_path, gemini_api_key=SecretStr("fixture-only"), gemini_model="fixture"))
    with pytest.raises(ProviderError) as error:
        provider.generate_json("fixture", ResearchBrief)
    assert "fixture-private-marker" not in str(error.value)
    assert not transient_gemini(client.models.generate_content.side_effect)


def test_cli_hides_validation_input(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    import agents.researcher as module
    monkeypatch.setattr("sys.argv", ["researcher", "Fixture"])
    def invalid_settings() -> Settings:
        raise ValidationError.from_exception_data("Settings", [{"type": "int_parsing", "loc": ("retry_attempts",),
                                                                "input": "fixture-private-marker"}])
    monkeypatch.setattr(module, "get_settings", invalid_settings)
    assert module.main() == 1
    captured = capsys.readouterr()
    assert "fixture-private-marker" not in captured.out + captured.err


def test_actual_sdk_serializes_schema_with_mock_transport(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    from google import genai
    from google.genai import types
    sent: list[httpx.Request] = []
    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "{}"}], "role": "model"},
                                                       "finishReason": "STOP"}]})
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        client = genai.Client(api_key="fixture-only", http_options=types.HttpOptions(httpx_client=http))
        monkeypatch.setattr("providers.llm_gemini.genai.Client", Mock(return_value=client))
        provider = GeminiProvider(Settings(root_dir=tmp_path, gemini_api_key=SecretStr("fixture-only"), gemini_model="fixture"))
        assert provider.generate_json("fixture", ResearchBrief) == "{}"
        assert len(sent) == 1
        import json
        payload = json.loads(sent[0].content)
        assert payload["generationConfig"]["responseMimeType"] == "application/json"
        assert "responseSchema" not in payload["generationConfig"]
        wire_schema = payload["generationConfig"]["responseJsonSchema"]
        assert "additionalProperties" not in wire_schema
        assert "anyOf" not in str(wire_schema)
        assert "TransportFact" in wire_schema["$defs"]
        assert "additional_properties" not in json.dumps(payload)
        provider.close()


@pytest.mark.parametrize("reason,retryable", [("MAX_TOKENS", True), ("SAFETY", False)])
def test_response_finish_status_is_not_silently_treated_as_json(reason: str, retryable: bool,
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from google.genai import types
    client = Mock()
    client.models.generate_content.return_value = types.GenerateContentResponse(candidates=[
        types.Candidate(finish_reason=reason, content=types.Content(parts=[types.Part(text="partial")]))])
    monkeypatch.setattr("providers.llm_gemini.genai.Client", Mock(return_value=client))
    provider = GeminiProvider(Settings(root_dir=tmp_path, gemini_api_key=SecretStr("fixture-only"), gemini_model="fixture"))
    with pytest.raises(GeminiOutputError) as error:
        provider.generate_json("fixture", ResearchBrief)
    assert error.value.retryable is retryable
    assert reason in provider.diagnostics.path.read_text(encoding="utf-8")
    if reason == "MAX_TOKENS":
        assert provider.output_token_budget == 16384


def test_empty_response_and_prompt_safety_are_diagnosed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from google.genai import types
    client = Mock()
    monkeypatch.setattr("providers.llm_gemini.genai.Client", Mock(return_value=client))
    provider = GeminiProvider(Settings(root_dir=tmp_path, gemini_api_key=SecretStr("fixture-only"), gemini_model="fixture"))
    client.models.generate_content.return_value = types.GenerateContentResponse()
    with pytest.raises(GeminiOutputError) as error:
        provider.generate_json("fixture", ResearchBrief)
    assert error.value.retryable
    client.models.generate_content.return_value = types.GenerateContentResponse(
        prompt_feedback=types.GenerateContentResponsePromptFeedback(block_reason="SAFETY"))
    with pytest.raises(GeminiOutputError) as error:
        provider.generate_json("fixture", ResearchBrief)
    assert not error.value.retryable
