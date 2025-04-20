# test_framework.py
from typing import List, Dict, Any, Optional, Union
import asyncio
import logging
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage, ToolMessage
from langchain_core.agents import AgentAction, AgentFinish
import json

logger = logging.getLogger("test_framework")

class MockModel:
    """Mock model that returns predefined responses for testing."""
    
    def __init__(self, responses=None):
        """Initialize with predefined responses."""
        self.responses = responses or []
        self.call_count = 0
        
    async def ainvoke(self, messages, config=None):
        """Mock the model's invoke method."""
        if not self.responses:
            # Default mock response if none provided
            return AIMessage(content="This is a mock response for testing.")
        
        # Get the next response or the last one if we've exhausted the list
        idx = min(self.call_count, len(self.responses) - 1)
        response_data = self.responses[idx]
        self.call_count += 1
        
        # Create either a regular message or a tool call based on the response data
        if "tool_calls" in response_data:
            return AIMessage(
                content=response_data.get("content", "I need to use a tool."),
                tool_calls=response_data["tool_calls"]
            )
        else:
            return AIMessage(content=response_data.get("content", "Mock response"))

class TestRunner:
    """Runner for testing agent workflows with predefined scenarios."""
    
    def __init__(self, agent_graph):
        """Initialize with an agent graph."""
        self.agent_graph = agent_graph
    
    async def run_test_case(self, test_case):
        """Run a single test case through the agent graph."""
        logger.info(f"Running test case: {test_case.get('name', 'Unnamed test')}")
        
        # Initialize state for this test
        initial_state = {
            "messages": [],
            "test": True,
            "test_responses": test_case.get("model_responses", []),
            "system_prompt": test_case.get("system_prompt"),
            "design_template": test_case.get("design_template"),
            "model_name": test_case.get("model_name", "gpt-4.1"),
            "cwd": test_case.get("cwd", "."),
            "intermediate_steps": []
        }
        
        # Add initial messages if specified
        if test_case.get("initial_messages"):
            initial_state["messages"] = test_case["initial_messages"]
        
        # Add input message if specified
        if test_case.get("input"):
            initial_state["messages"].append(HumanMessage(content=test_case["input"]))
        
        # Run the agent
        try:
            result = await self.agent_graph.ainvoke(initial_state)
            
            # Validate results if validation criteria provided
            if test_case.get("validation"):
                validation_result = self._validate_results(result, test_case["validation"])
                return {
                    "name": test_case.get("name", "Unnamed test"),
                    "success": validation_result["success"],
                    "details": validation_result.get("details", ""),
                    "result": result
                }
            
            return {
                "name": test_case.get("name", "Unnamed test"),
                "success": True,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Test failed with exception: {str(e)}")
            return {
                "name": test_case.get("name", "Unnamed test"),
                "success": False,
                "error": str(e)
            }
    
    async def run_test_suite(self, test_suite):
        """Run a suite of test cases and return aggregated results."""
        results = []
        
        for test_case in test_suite:
            result = await self.run_test_case(test_case)
            results.append(result)
        
        success_count = sum(1 for r in results if r["success"])
        
        return {
            "total": len(results),
            "successful": success_count,
            "failed": len(results) - success_count,
            "success_rate": success_count / len(results) if results else 0,
            "detailed_results": results
        }
    
    def _validate_results(self, result, validation_criteria):
        """Validate test results against provided criteria."""
        success = True
        details = []
        
        # Check for expected messages
        if "expected_messages" in validation_criteria:
            expected_count = validation_criteria["expected_messages"]
            actual_count = len(result.get("messages", []))
            if actual_count != expected_count:
                success = False
                details.append(f"Expected {expected_count} messages, got {actual_count}")
        
        # Check for specific content in the last message
        if "contains_content" in validation_criteria:
            expected_content = validation_criteria["contains_content"]
            last_message = result.get("messages", [])[-1] if result.get("messages") else None
            
            if not last_message or not isinstance(last_message, AIMessage):
                success = False
                details.append("No AI message found in results")
            elif not expected_content in last_message.content:
                success = False
                details.append(f"Expected content not found in message: {expected_content}")
        
        # Check for expected tool calls
        if "expected_tool_calls" in validation_criteria:
            expected_tools = validation_criteria["expected_tool_calls"]
            found_tools = []
            
            for step in result.get("intermediate_steps", []):
                if isinstance(step[0], AgentAction):
                    found_tools.append(step[0].tool)
            
            for tool in expected_tools:
                if tool not in found_tools:
                    success = False
                    details.append(f"Expected tool call not found: {tool}")
        
        return {
            "success": success,
            "details": details
        }

# Helper function to create test cases
def create_test_case(name, input_message, model_responses, 
                    system_prompt=None, design_template=None,
                    validation=None, initial_messages=None):
    """Helper to create standardized test cases."""
    return {
        "name": name,
        "input": input_message,
        "model_responses": model_responses,
        "system_prompt": system_prompt,
        "design_template": design_template,
        "validation": validation,
        "initial_messages": initial_messages or []
    }

# Sample test suite that can be extended
SAMPLE_TEST_SUITE = [
    create_test_case(
        name="Basic response test",
        input_message="Hello, can you help me?",
        model_responses=[
            {"content": "I'd be happy to help you! What do you need assistance with today?"}
        ],
        validation={"expected_messages": 2}
    ),
    create_test_case(
        name="Tool use test",
        input_message="What files are in the current directory?",
        model_responses=[
            {
                "content": "I'll check the current directory for you.",
                "tool_calls": [
                    {
                        "name": "list_directory",
                        "args": {"path": "."}
                    }
                ]
            },
            {"content": "Here are the files in the current directory: test.py, graph.py, etc."}
        ],
        validation={
            "expected_tool_calls": ["list_directory"],
            "expected_messages": 3
        }
    )
]