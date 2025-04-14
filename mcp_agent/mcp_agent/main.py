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
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import asyncio
from langchain_openai import ChatOpenAI as LC_ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_mcp_tools import convert_mcp_to_langchain_tools
from langgraph.checkpoint.memory import MemorySaver
import json
from contextlib import asynccontextmanager
from json import JSONEncoder
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from .prompt import get_prompt

#from .prompt import get_prompt

load_dotenv()

# Update the MCPAgent class with these key changes
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
        self.agent_executor = None
        self.cleanup_func = None
        self.config = {"configurable": {"thread_id": "42"}}
        self.output_parser = None   # Placeholder for output parser
        self.human_in_the_loop = False
        self.prompt = self.create_prompt(os.getcwd())

        self.checkpointer = MemorySaver()

    def create_prompt(self, cwd: str) -> SystemMessage:
        system_message = get_prompt(cwd)
        return SystemMessage(
            content=system_message
        )

    async def initialize(self):
        self.tools, self.cleanup_func = await convert_mcp_to_langchain_tools(self.mcp_servers)
        if self.tools:
            self.agent_executor = create_react_agent(
                self.llm,
                tools=self.tools,
                prompt=self.prompt,
                checkpointer=self.checkpointer,
                #interrupt_before=["tools"],
            )
        else:
            raise Exception("No tools were loaded from MCP servers")

    # Add output formatting middleware
    async def format_response(self, content: str) -> str:
        """Ensure proper XML tag formatting in model responses"""
        content = content.replace("<boltArtifact", "\n<boltArtifact")
        content = content.replace("</boltArtifact>", "</boltArtifact>\n")
        return content

    async def astream_events(self, query: str, config: dict):
        inputs = {
            "messages": 
            [HumanMessage(content=query),
            self.prompt
            ]
        }

        async for event in self.agent_executor.astream_events(
            inputs,
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
    llm = LC_ChatOpenAI(
        temperature=0,
        model="gpt-4o",
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    app.state.agent = MCPAgent(llm)
    await app.state.agent.initialize() # Initialize the agent
    app.state.agent.create_prompt(os.getcwd())  # Initialize the prompt



@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state.agent, 'cleanup'):
        await app.state.agent.cleanup()

# ... (keep previous imports and setup)

# Update the chat endpoint
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        user_messages = [msg for msg in request.messages if msg["role"] == "user"]
        if not user_messages:
            raise HTTPException(status_code=400, detail="No user message found")
        latest_user_message = user_messages[-1]["content"]
        print(f"Latest user message: {latest_user_message}")
        
        async def event_stream():
            config = {"configurable": {"thread_id": request.thread_id}}
            artifact_stack = []  # Track nested artifacts
            buffer = ""  # Buffer for incomplete tags

            async for event in app.state.agent.astream_events(
                query=latest_user_message,
                config=config
            ):
                if event["event"] == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    content = chunk.content
                    
                    # Process the content with any buffered data from previous chunks
                    to_process = buffer + content
                    buffer = ""
                    
                    while to_process:
                        if artifact_stack:
                            # Inside an artifact - look for closing tag
                            close_pos = to_process.find("</boltArtifact>")
                            if close_pos != -1:
                                # Found closing tag - emit content up to close tag
                                artifact_content = to_process[:close_pos]
                                yield json.dumps({'text': artifact_content})
                                
                                # Emit closing tag
                                yield json.dumps({'text': '</boltArtifact>'})
                                
                                artifact_stack.pop()
                                to_process = to_process[close_pos + len("</boltArtifact>"):]
                            else:
                                # No closing tag yet - buffer all content
                                yield json.dumps({'text': to_process})
                                break
                        else:
                            # Outside artifact - look for opening tag
                            open_pos = to_process.find("<boltArtifact")
                            if open_pos != -1:
                                # Found opening tag - emit content before tag
                                if open_pos > 0:
                                    plain_text = to_process[:open_pos]
                                    yield json.dumps({'text': plain_text})
                                
                                # Find end of opening tag
                                tag_end_pos = to_process.find(">", open_pos)
                                if tag_end_pos != -1:
                                    # Complete tag found - emit it
                                    tag_content = to_process[open_pos:tag_end_pos + 1]
                                    yield json.dumps({'text': tag_content})
                                    
                                    artifact_stack.append(True)  # Mark we're in an artifact
                                    to_process = to_process[tag_end_pos + 1:]
                                else:
                                    # Incomplete tag - buffer for next chunk
                                    buffer = to_process[open_pos:]
                                    break
                            else:
                                # No tags - emit all as plain text
                                yield json.dumps({'text': to_process})
                                break

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))