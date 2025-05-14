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
from typing import List, Dict, Any, Optional # Added Any, Optional
import os
from dotenv import load_dotenv
from langchain_core.messages import (
    HumanMessage, AIMessage, SystemMessage, BaseMessage)
import asyncio


import logging # Add logging import
import uuid

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


from .mcp_agent import MCPAgent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define a more specific type for the message data if needed, or use Any
class MessageData(BaseModel):
    imageData: Optional[str] = None

class ChatMessage(BaseModel):
    role: str
    content: str
    data: Optional[MessageData] = None

class ChatRequest(BaseModel):
    messages: List[ChatMessage] # Use the new ChatMessage model
    thread_id: str = "default"
    stream: bool = True
    use_reasoning: bool = False

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
    logger.info("--- Entering chat_endpoint ---") # Log entry
    # Convert request messages to BaseMessage instances
    await app.state.agent.set_agent_type(reasoning=request.use_reasoning)
    print(f"Agent set to reasoning: {request.use_reasoning}")
    try:
        langchain_messages: List[BaseMessage] = [] # Renamed and typed for clarity
        num_messages = len(request.messages)
        for i, msg in enumerate(request.messages):
            role = msg.role
            content = msg.content
            is_last_message = (i == num_messages - 1) # Restore check

            if role == 'user':
                # Restore multimodal check for the last message
                image_data = msg.data.imageData if msg.data and msg.data.imageData and is_last_message else None

                if image_data:
                    # Create multimodal message if image data exists in the last message
                    message_content = [
                        {"type": "text", "text": content},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_data} # Assuming image_data is a base64 data URL
                        }
                    ]
                    langchain_messages.append(HumanMessage(content=message_content))
                    print(f"Processed multimodal user message: {content[:50]}... + Image")
                else:
                    # Regular text message
                    langchain_messages.append(HumanMessage(content=content))
            elif role == 'assistant':
                 # Handle assistant messages if needed
                 langchain_messages.append(AIMessage(content=content))
            # Add other roles (system, tool) if necessary

        print(f"Processed LangChain messages: {langchain_messages}") # Updated print statement

        async def event_stream():
            """Stream formatted content directly from the agent's artifact stream."""
            async for content in app.state.agent.stream_xml_content(
                input=langchain_messages,
            ):
                
                # Direct yield without additional processing
                yield content
                    
        print("Finished graph execution!")
        return StreamingResponse(event_stream(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
