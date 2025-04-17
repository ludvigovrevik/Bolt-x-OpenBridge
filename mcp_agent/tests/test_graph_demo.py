import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock

from app.graph_demo import (
    get_model,
    AppDevState,
    get_plan_step,
    get_execution_agent,
    create_agent_graph
)

@pytest.mark.asyncio
async def test_get_model():
    # Test with test=True should return MockChatModel
    model = await get_model(test=True)
    assert model.__class__.__name__ == "MockChatModel"
    
    # Test mock model generation
    messages = [MagicMock(content="create a detailed step-by-step plan")]
    result = await model._agenerate(messages)
    # Parse the JSON string to verify it contains steps
    content = json.loads(result.generations[0].message.content)
    assert "steps" in content
    assert len(content["steps"]) > 0

@pytest.mark.asyncio
async def test_plan_step():
    # Setup mock state
    state = AppDevState(
        input="Create a todo app",
        design_template="React app",
        model_name="test-model",
        test=True
    )
    
    # Get plan step function
    plan_step_func = await get_plan_step()
    
    # Execute plan step
    result = await plan_step_func(state)
    
    # Verify result contains app_plan
    assert "app_plan" in result
    assert isinstance(result["app_plan"], list)
    assert len(result["app_plan"]) > 0