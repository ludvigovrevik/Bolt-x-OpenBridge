###################################################################
# Dette er en demo av hvordan vi kan bruke MCP agent i langchain

# Dette er source code for use MCP agenten som jeg brukte som base
# https://github.com/mcp-use/mcp-use/blob/main/mcp_use/agents/mcpagent.py

# MCP Agent for LangChain
# Dette er source code for å gjøre MCP til langchain tools
# https://github.com/hideya/langchain-mcp-tools-py?tab=readme-ov-file

# further on this is one way we can create more complex systems
# https://github.com/roboticsocialism/langgraph_demo/blob/main/langgraph_demo.py

# This is how we can create human in the loop using the standard scrathpad agent
# https://langchain-ai.github.io/langgraph/how-tos/create-react-agent-hitl/#code

####################################################################

# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    HumanMessage, AIMessage, SystemMessage, BaseMessage)
import asyncio
from langgraph.prebuilt import create_react_agent
from langchain_mcp_tools import convert_mcp_to_langchain_tools
from langgraph.checkpoint.memory import MemorySaver
import json
import json # Add json import
from contextlib import asynccontextmanager
from json import JSONEncoder
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from .prompts.artifact_prompt import get_prompt
from .load_model import load_model
from .graph_demo import create_agent_graph, AgentState
#from .prompt import get_prompt

load_dotenv()

class ConfigLLM(BaseModel):
    model_name: str = os.getenv("LLM_MODEL_NAME", "gpt-4o")
    temperature: float = 0.0

# Update the MCPAgent class with these key changes
class MCPAgent:
    def __init__(self):
        self.llm = ConfigLLM()
        # Update repo_root to point to Bolt-x-OpenBridge (3 dirs up from main.py)
        current_file_path = os.path.abspath(__file__)
        self.repo_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
        self.frontend = os.path.join(self.repo_root, "app")
        print(self.repo_root)
        self.mcp_servers = {
            "filesystem": {
                "command": "npx",
                "args": [
                    "-y",  # Crucial for non-interactive execution
                    "@modelcontextprotocol/server-filesystem",
                    os.path.expanduser(self.repo_root)  # Home directory as root
                ],
                "cwd": os.path.expanduser(self.repo_root)  # Explicit working directory
            },
            "mcp-figma": {
                "command": "npx",
                "args": [
                    "-y", 
                    "mcp-figma"
                ]
            },  
            "sequential-thinking": {
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-sequential-thinking"
                ]
            }, 
            }
        self.tools = None
        self.cleanup_func = None
        self.config = {"configurable": {"thread_id": "42"}}
        self.output_parser = None   # Placeholder for output parser
        self.human_in_the_loop = False
        self.prompt = None
        self.graph = None
        self.checkpointer = MemorySaver()

    def create_prompt(self, cwd: str) -> ChatPromptTemplate:
        return [SystemMessage(content=get_prompt(cwd, self.tools))]

    async def initialize(self):
        self.tools, self.cleanup_func = await convert_mcp_to_langchain_tools(self.mcp_servers)
        # Remove the nested initialize function and create the graph directly
        if self.tools:
            self.graph = create_agent_graph(
                self.tools,
                self.prompt,
                self.checkpointer
            )
        else:
            raise Exception("No tools were loaded from MCP servers")
        
    # Add output formatting middleware
    async def format_response(self, content): # Removed type hint for flexibility
        """Ensure proper XML tag formatting in model responses"""
        if isinstance(content, str): # Check if content is a string
            content = content.replace("<boltArtifact", "\n<boltArtifact")
            content = content.replace("</boltArtifact>", "</boltArtifact>\n")
        # If not a string, return content as is
        return content

    async def astream_events(self, input: List[BaseMessage], config: dict):
        # Convert input messages to AgentState format
        initial_state = AgentState(
            cwd=os.getcwd(),
            model_name=self.llm.model_name,
            messages=input,
            agent_outcome=None,
            return_direct=False,
            intermediate_steps=[]
        )

        # Use proper input format for the graph
        async for event in self.graph.astream_events(
            initial_state,
            config=config,
            stream_mode="values"
        ):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                chunk.content = await self.format_response(chunk.content)
                yield event

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    thread_id: str = "default"
    stream: bool = True

@app.on_event("startup")
async def startup_event():
    app.state.agent = MCPAgent()
    await app.state.agent.initialize() # Initialize the agent
    # Additional setup if needed
    print("Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state.agent, 'cleanup'):
        await app.state.agent.cleanup()
    # Additional cleanup if needed
    print("Application shutdown complete")


@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    # Convert request messages to BaseMessage instances
    try:
        user_messages = []
        for msg in request.messages:
            role = msg['role']
            content = msg['content']
            if role == 'user':
                user_messages.append(HumanMessage(content=content))  # Fixed variable name

        print(f"Processed messages: {user_messages}")

        async def event_stream():
            config = {"configurable": {"thread_id": request.thread_id}}
            artifact_stack = []  # Track nested artifacts
            buffer = ""  # Buffer for incomplete tags

            async for event in app.state.agent.astream_events(
                input=user_messages,
                config=config
            ):
                if event["event"] == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    content = chunk.content
                    processed_content = "" # Accumulator for text from structured chunks

                    if isinstance(content, str):
                        processed_content = content
                    elif isinstance(content, list):
                        # Handle list content (likely from Anthropic)
                        for item in content:
                            if isinstance(item, dict) and 'text' in item and isinstance(item['text'], str):
                                processed_content += item['text']
                        if not processed_content: # If no text was extracted
                             print(f"Warning: List chunk did not contain expected 'text' field: {content}")
                             continue # Skip this chunk
                    else:
                        # Skip other unexpected types
                        print(f"Warning: Skipping unexpected content type: {type(content)}")
                        continue

                    # Process the extracted/original content string with any buffered data
                    to_process = buffer + processed_content
                    buffer = ""

                    while to_process:
                        if artifact_stack:
                            # Inside an artifact - look for closing tag
                            close_pos = to_process.find("</boltArtifact>")
                            if close_pos != -1:
                                # Found closing tag - emit content up to close tag
                                artifact_content = to_process[:close_pos]
                                yield artifact_content

                                # Emit closing tag
                                yield '</boltArtifact>'

                                artifact_stack.pop()
                                to_process = to_process[close_pos + len("</boltArtifact>"):]
                            else:
                                # No closing tag yet - buffer all content
                                buffer = to_process
                                break
                        else:
                            # Outside artifact - look for opening tag
                            open_pos = to_process.find("<boltArtifact")
                            if open_pos != -1:
                                # Found opening tag - emit content before tag
                                if open_pos > 0:
                                    plain_text = to_process[:open_pos]
                                    yield plain_text

                                # Find end of opening tag
                                tag_end_pos = to_process.find(">", open_pos)
                                if tag_end_pos != -1:
                                    # Complete tag found - emit it
                                    tag_content = to_process[open_pos:tag_end_pos + 1]
                                    yield tag_content

                                    artifact_stack.append(True)  # Mark we're in an artifact
                                    to_process = to_process[tag_end_pos + 1:]
                                else:
                                    # Incomplete tag - buffer for next chunk
                                    buffer = to_process[open_pos:]
                                    break
                            else:
                                # No tags - emit all as plain text
                                yield to_process
                                break

            final_state = app.state.agent.graph.get_state(config).values
            print(f"Final state: {final_state}")

        print("Finished graph execution!")
        return StreamingResponse(event_stream(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
