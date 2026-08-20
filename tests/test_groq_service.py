from __future__ import annotations
import pytest
import httpx
from unittest.mock import patch, MagicMock
from app.services.groq_service import extract_mention_and_citations

@patch.dict('os.environ', {'GROQ_API_KEY': 'fake-key'})
@patch('app.services.groq_service.httpx.Client.post')
def test_extract_mention_and_citations_success(mock_post):
    # Mocking Groq API response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"mentioned": true, "cited_pages": [{"page": "https://example.com/pricing", "prompt_count": 2}]}'
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    result = extract_mention_and_citations(
        raw_response="Yes, example.com is a great site. Visit https://example.com/pricing.",
        client_domain="example.com",
        client_name="Example Corp"
    )

    assert result["mentioned"] is True
    assert len(result["cited_pages"]) == 1
    assert result["cited_pages"][0]["page"] == "https://example.com/pricing"
    assert result["cited_pages"][0]["prompt_count"] == 2

@patch.dict('os.environ', {'GROQ_API_KEY': 'fake-key'})
@patch('app.services.groq_service.httpx.Client.post')
def test_extract_mention_and_citations_json_decode_error(mock_post):
    # LLM hallucinates non-JSON
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "I couldn't find any mentions of example.com."
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    result = extract_mention_and_citations(
        raw_response="Random text here.",
        client_domain="example.com",
        client_name="Example Corp"
    )

    assert result["mentioned"] is False
    assert result["cited_pages"] == []

def test_extract_mention_and_citations_no_api_key():
    with patch.dict('os.environ', clear=True):
        with pytest.raises(ValueError, match="GROQ_API_KEY is not set"):
            extract_mention_and_citations(
                raw_response="text",
                client_domain="example.com",
                client_name="Example Corp"
            )
