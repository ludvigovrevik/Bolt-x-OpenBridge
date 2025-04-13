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
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
import asyncio
from langchain_openai import ChatOpenAI as LC_ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_mcp_tools import convert_mcp_to_langchain_tools

load_dotenv()

# Update the MCPAgent class
class MCPAgent:
    def __init__(self, llm):
        self.llm = llm
        self.mcp_servers = {
            "filesystem": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-filesystem", os.getcwd()]
            }
        }
        self.tools = None
        self.agent_executor = None  # Changed from self.agent for clarity
        self.cleanup_func = None
        self.config = {"configurable": {"thread_id": "42"}}

    async def initialize(self):
        self.tools, self.cleanup_func = await convert_mcp_to_langchain_tools(self.mcp_servers)
        if self.tools:
            self.agent_executor = create_react_agent(self.llm, self.tools)
        else:
            raise Exception("No tools were loaded from MCP servers")

    # Add context manager support
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def astream_events(self, query, config, chat_history=None):
        inputs = {"messages": [HumanMessage(content=query)]}
        async for event in self.agent_executor.astream_events(
            inputs, 
            config=config,
            stream_mode="values"
        ):
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
    llm = LC_ChatOpenAI(
        temperature=0,
        model="gpt-4o",
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    app.state.agent = MCPAgent(llm)
    await app.state.agent.initialize() # Initialize the agent on startup

@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state.agent, 'cleanup'):
        await app.state.agent.cleanup()

# Update the chat endpoint
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        user_messages = [msg for msg in request.messages if msg["role"] == "user"]
        if not user_messages:
            raise HTTPException(status_code=400, detail="No user message found")
        latest_user_message = user_messages[-1]["content"]

        async def event_stream():
            config = {"configurable": {"thread_id": request.thread_id}}
            in_artifact = False  # Track artifact state
            content_buffer = ""
            
            event_stream = app.state.agent.astream_events(
                query=latest_user_message,
                config=config
            )
            
            async for event in event_stream:
                if event["event"] == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    content = chunk.content
                    
                    # Handle artifact detection
                    if "<boltArtifact" in content:
                        in_artifact = True
                        content_buffer = ""
                    if "</boltArtifact>" in content:
                        in_artifact = False
                        content_buffer += content
                        yield f"data: {json.dumps({'text': content_buffer, 'inArtifact': True})}\n\n"
                        content_buffer = ""
                        continue
                        
                    if in_artifact:
                        content_buffer += content
                    else:
                        yield f"{json.dumps({'text': content, 'inArtifact': False})}\n\n"
            
            yield "data: DONE\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))