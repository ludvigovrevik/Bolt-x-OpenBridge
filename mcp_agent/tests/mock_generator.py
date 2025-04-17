# Mock LLM for testing
class MockChatModel(BaseChatModel):
    """Mock Chat Model for testing purposes"""
    
    def __init__(self):
        super().__init__()
   
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        """Synchronous generate method required by BaseChatModel"""
        raise NotImplementedError("MockChatModel only supports async generation")
    
    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        """Mock generation method that returns predetermined responses based on the prompt"""
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, ChatResult
        import json
        
        prompt = messages[0].content if messages else ""
        
        # Return different mock responses based on the content of the prompt
        if "create a detailed step-by-step plan" in prompt.lower():
            # Return a mock plan - use JSON string instead of dict
            steps = [
                "Create project structure",
                "Set up React components",
                "Implement state management",
                "Add styling"
            ]
            # For structured output, use JSON string format
            content = json.dumps({"steps": steps})
            response = AIMessage(content=content)
        elif "executing step" in prompt.lower():
            # Mock file content generation
            step = prompt.split("executing step:")[1].strip().split("\n")[0] if "executing step:" in prompt else "Unknown step"
            
            if "project structure" in step.lower():
                content = "// Project structure setup\nconsole.log('Project structure created');"
            elif "react components" in step.lower():
                content = "import React from 'react';\n\nfunction Component() {\n  return <div>Mock Component</div>;\n}\n\nexport default Component;"
            elif "state management" in step.lower():
                content = "import { createContext, useReducer } from 'react';\n\nexport const AppContext = createContext();\n\nconst initialState = { tasks: [] };"
            elif "styling" in step.lower():
                content = ".component {\n  color: #4a90e2;\n  background-color: #f5f5f5;\n}"
            else:
                content = f"// Mock implementation for: {step}"
                
            response = AIMessage(content=content)
        else:
            # Default mock response
            content = "Mock response for testing purposes."
            response = AIMessage(content=content)
        
        generation = ChatGeneration(message=response)
        return ChatResult(generations=[generation])
    
    @property
    def _llm_type(self):
        return "mock-chat-model"
    
# Mock implementation of get_prompt function
def get_mock_prompt(cwd: str, design_template: str) -> str:
    """
    Get formatting instructions for the current working directory.
    This function returns a system message with formatting instructions.
    """
    return f"""You are creating files in the directory: {cwd}

FORMATTING INSTRUCTIONS:
{design_template}

Follow these instructions exactly when creating files. Do not add any filepath information or output modifications.
Return only the content of the file as plain text.
"""