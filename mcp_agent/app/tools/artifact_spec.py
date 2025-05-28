from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from ..graph import ArtifactSpec, ArtifactFile
from ..load_model import load_model

@tool(return_direct=True)
def artifact_spec(user_request: str) -> ArtifactSpec:
    """Generate an application spec from a user request.
    
    Args:
        user_request: Description of the application to build
        
    Returns:
        ArtifactSpec: Complete specification for the artifact including files, dependencies, and scripts
    """

    llm = load_model(model_name="gpt-4.1-nano")
    llm_with_struct = llm.with_structured_output(schema=ArtifactSpec, method="function_calling")

    system_prompt = """
You are an expert application architect. Analyze the user request and generate a complete ArtifactSpec.

**CRITICAL REQUIREMENTS:**
1. Choose appropriate framework/tools based on the request
2. Include ALL necessary dependencies and devDependencies
3. Include scripts with at least "dev" command
4. List ALL files needed for a working application
5. Use modern, production-ready versions

**FRAMEWORK EXAMPLES:**
- React: Vite, React 18+, appropriate plugins
- Vue: Vite, Vue 3+, appropriate plugins  
- Angular: Angular CLI, latest version
- Vanilla JS: Vite or Webpack, modern tooling
- Node.js: Express, appropriate middleware

**REQUIRED OUTPUTS:**
- artifact_id: kebab-case identifier
- title: descriptive name
- dependencies: runtime packages with versions
- devDependencies: build tools, bundlers, etc.
- scripts: dev, build, and other commands
- files: complete list of files needed (paths only)
"""

    user_prompt = f"""
Create a complete application specification for: {user_request}

Requirements:
1. Analyze the request to determine the best framework/tools
2. Provide complete dependency lists with modern versions
3. Include all necessary configuration files
4. List all application files needed
5. Ensure the "dev" script starts a development server

Make this production-ready and modern.
"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    llm = load_model(
        model_name="gpt-4.1-nano",
    )
        
    llm_with_struct = llm.with_structured_output(schema=ArtifactSpec, method="function_calling")

    # This is a placeholder - you would implement your actual spec generation logic here
    # For now, returning a basic React + Tailwind structure
    return llm_with_struct.invoke(messages)