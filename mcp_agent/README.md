# MCP Agent with LangChain Integration

A FastAPI application that integrates MCP (Model Context Protocol) with LangChain to create an intelligent agent system.

## Features

- MCP Agent implementation with LangChain tools
- OpenAI GPT-4.1 integration
- Streaming response API
- Human-in-the-loop capabilities
- Artifact handling with BoltArtifact XML tags
- Memory checkpointing for conversation history

## Prerequisites

- Python 3.9+
- Node.js (for MCP filesystem server)
- OpenAI API key

## Installation

1. Create and activate a virtual environment:
```bash
cd mcp_agent
python -m venv .venv
source .venv/bin/activate  # Linux/MacOS
# or 
.venv\Scripts\activate     # Windows
``` 

2. Install dependencies:
```bash
pip install -r requirements.txt
pip install -e .
```

3. Install dependencies:
```bash
pip install -r requirements.txt
pip install -e .
```

4. Set up environment variables:
```bash
nano .env
```
Then edit .env and add your OpenAI API key in this format:
OPENAI_API_KEY = "..."

## Running the Application

Development Mode
```bash
uvicorn mcp_agent.main:app --reload
```
or

Production Mode
```bash
uvicorn mcp_agent.main:app --host 0.0.0.0 --port 8000
```

## References
MCP Use agent using langchain
https://github.com/mcp-use/mcp-use/blob/main/mcp_use/agents/mcpagent.py

Transformation of MCP tools to langchain tools
https://github.com/hideya/langchain-mcp-tools-py?tab=readme-ov-file

Further on this is one way we can create more complex systems
https://github.com/roboticsocialism/langgraph_demo/blob/main/langgraph_demo.py

This is how we can create human in the loop using the standard scrathpad agent
https://langchain-ai.github.io/langgraph/how-tos/create-react-agent-hitl/#code


## Troubleshooting
If you encounter import errors:

1. Ensure you've run pip install -e .
2. Verify your PYTHONPATH includes the project root
3. Check all __init__.py files are present

For MCP server issues:

- Ensure Node.js is installed
- Check the MCP server starts properly
