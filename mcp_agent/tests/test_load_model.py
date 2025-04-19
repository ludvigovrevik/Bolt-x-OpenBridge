# tests/test_load_model.py
import pytest
from unittest.mock import patch, MagicMock

from app.load_model import load_model
from langchain_core.prompts import ChatPromptTemplate

@pytest.mark.asyncio
@patch('app.load_model.ChatOpenAI')
async def test_load_model_with_chat_prompt(mock_chat_openai):
    # Setup mock
    mock_instance = MagicMock()
    mock_chat_openai.return_value = mock_instance
    
    # Test with proper ChatPromptTemplate
    prompt = ChatPromptTemplate.from_template("Hello {name}")
    model = load_model(model_name="test-model", prompt=prompt)
    
    # Verify model was created properly
    mock_chat_openai.assert_called_once()
    assert model is not None