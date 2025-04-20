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
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    HumanMessage, AIMessage, SystemMessage, BaseMessage)
import asyncio
from langgraph.prebuilt import create_react_agent
from langchain_mcp_tools import convert_mcp_to_langchain_tools
from langgraph.checkpoint.memory import MemorySaver
import json
from langchain_core.prompts import ChatPromptTemplate
from .prompts.artifact_prompt import get_prompt
from .load_model import load_model
#from .graph import create_agent_graph, AgentState
from .graph_demo import (
    AgentState as ReasoningAgentState,
    create_reasoning_agent_graph,
    )
from .graph import create_agent_graph, AgentState
from .prompt import openbridge_example
#from .prompt import get_prompt
import logging # Add logging import

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConfigLLM(BaseModel):
    model_name: str = os.getenv("LLM_MODEL_NAME", "gpt-4.1")
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
#             "sequential-thinking": {
#                 "command": "npx",
#                 "args": [
#                     "-y",
#                     "@modelcontextprotocol/server-sequential-thinking"
#                 ]
#             },
            }
        self.tools = None
        self.cleanup_func = None
        self.config = {"configurable": {"thread_id": "42"}}
        self.output_parser = None   # Placeholder for output parser
        self.human_in_the_loop = False
        self.prompt = None
        self.graph = None
        self.checkpointer = MemorySaver()
        self.reasoning_agent = None
        self.initialized = False
    
    async def set_agent_type(self, reasoning: bool = False):
        """Set the agent type and reinitialize the graph if needed"""
        if self.reasoning_agent == reasoning and self.initialized:
            # No change needed
            logger.info(f"Agent already set to {'reasoning' if reasoning else 'standard'} type")
            return
            
        logger.info(f"Changing agent type from {'reasoning' if self.reasoning_agent else 'standard'} to {'reasoning' if reasoning else 'standard'}")
        self.reasoning_agent = reasoning
        
        # Only rebuild graph if we've already initialized
        if self.initialized and self.tools:
            logger.info(f"Rebuilding graph for {'reasoning' if reasoning else 'standard'} agent")
            
            if self.reasoning_agent:
                self.graph = await create_reasoning_agent_graph(
                    self.tools,
                    self.checkpointer,
                )
            else:
                self.graph = create_agent_graph(
                    self.tools,
                    self.checkpointer
                )
            return True
        return False

    async def initialize(self):
        self.tools, self.cleanup_func = await convert_mcp_to_langchain_tools(self.mcp_servers)
        
        if self.tools:
            print("MCP tools loaded successfully")
            self.initialized = True  # Set flag to True after successful initialization
            if self.reasoning_agent:
                self.graph = await create_reasoning_agent_graph(
                    self.tools,
                    self.checkpointer,
                )
            else:
                self.graph = create_agent_graph(
                    self.tools,
                    self.checkpointer
                )
        
        else:
            raise Exception("No tools were loaded from MCP servers")

    def create_prompt(self, cwd: str) -> ChatPromptTemplate:
        return [SystemMessage(content=get_prompt(cwd, self.tools))]

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
        if self.reasoning_agent:
            # Use the reasoning agent graph if available
            initial_state = ReasoningAgentState(
                cwd=os.getcwd(),
                model_name=self.llm.model_name,
                input=input,
            )
            print(f"Using reasoning agent graph")
        else:
            # Use the standard agent graph
            initial_state = AgentState(
                cwd=os.getcwd(),
                model_name=self.llm.model_name,
                messages=input,
            )
            print(f"Using standard agent graph")
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

    async def cleanup(self):
        """Clean up MCP servers and other resources."""
        if self.cleanup_func:
            try:
                await self.cleanup_func()
                print("MCP tools cleanup completed successfully")
            except Exception as e:
                print(f"Error during MCP tools cleanup: {e}")
        else:
            print("No cleanup function available")
        # Reset initialized state
        self.initialized = False

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
    use_reasoning: bool = True

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
            config = {"configurable": {"thread_id": request.thread_id}}
            artifact_stack = []  # Track nested artifacts
            buffer = ""  # Buffer for incomplete tags

            logger.info("--- Starting agent event stream ---") # Log before loop
            async for event in app.state.agent.astream_events(
                input=langchain_messages, # Corrected: Pass the list directly
                config=config
                # Removed incorrect stream_mode argument here
            ):
                event_name = event.get("event")
                #logger.info(f"--- Agent Event Received: {event_name} ---") # Log inside loop

                # Focus ONLY on the event carrying content chunks from the LLM stream
                if event_name == "on_chat_model_stream":
                    chunk_data = event.get("data", {}).get("chunk")
                    if not chunk_data:
                        logger.warning("Event 'on_chat_model_stream' had no chunk data.")
                        continue

                    # Extract content from the chunk (AIMessageChunk)
                    content = chunk_data.content
                    if content is None: # Skip if content is None
                        continue

                    logger.debug(f"Raw chunk content: {content}") # Debug log for raw content

                    # --- Process and Yield Logic ---
                    processed_content = "" # Accumulator for text from structured chunks (if applicable)
                    if isinstance(content, str):
                        processed_content = content
                    elif isinstance(content, list): # Handle potential list format (e.g., Anthropic)
                        for item in content:
                            if isinstance(item, dict) and 'text' in item and isinstance(item['text'], str):
                                processed_content += item['text']
                        if not processed_content:
                             logger.warning(f"List chunk did not contain expected 'text' field: {content}")
                             continue
                    else:
                        logger.warning(f"Skipping unexpected content type in chunk: {type(content)}")
                        continue

                    # Process the extracted/original content string with any buffered data
                    to_process = buffer + processed_content
                    buffer = "" # Clear buffer before processing

                    logger.debug(f"Processing content for yielding: '{to_process}'")

                    # --- Artifact Parsing Logic (remains the same) ---
                    while to_process:
                        if artifact_stack:
                            # Inside an artifact - look for closing tag
                            close_pos = to_process.find("</boltArtifact>")
                            if close_pos != -1:
                                # Found closing tag - yield content up to close tag
                                artifact_content = to_process[:close_pos]
                                # Removed logging
                                yield artifact_content

                                # Emit closing tag
                                # Removed logging
                                yield '</boltArtifact>'

                                artifact_stack.pop()
                                to_process = to_process[close_pos + len("</boltArtifact>"):]
                            else:
                                # No closing tag yet - buffer all content
                                buffer = to_process
                                logger.debug(f"Buffering inside artifact: '{buffer}'")
                                break
                        else:
                            # Outside artifact - look for opening tag
                            open_pos = to_process.find("<boltArtifact")
                            if open_pos != -1:
                                # Found opening tag - yield content before tag
                                if open_pos > 0:
                                    plain_text = to_process[:open_pos]
                                    # Removed logging
                                    yield plain_text

                                # Find end of opening tag
                                tag_end_pos = to_process.find(">", open_pos)
                                if tag_end_pos != -1:
                                    # Complete tag found - yield it
                                    tag_content = to_process[open_pos:tag_end_pos + 1]
                                    # Removed logging
                                    yield tag_content

                                    artifact_stack.append(True)  # Mark we're in an artifact
                                    to_process = to_process[tag_end_pos + 1:]
                                else:
                                    # Incomplete tag - buffer for next chunk
                                    buffer = to_process[open_pos:]
                                    logger.debug(f"Buffering incomplete opening tag: '{buffer}'")
                                    break
                            else:
                                # No tags - yield all as plain text
                                # Removed logging
                                yield to_process
                                to_process = "" # Ensure loop terminates
                                break
                # --- End of Artifact Parsing Logic ---
                # else: # Optionally handle other event types if needed for debugging
                #    logger.info(f"Other event data: {event.get('data')}")

            # Handle any remaining buffer content after the loop finishes
            if buffer:
                # Removed logging
                yield buffer

            # Final state logging (optional, might be noisy)
            # final_state = app.state.agent.graph.get_state(config).values
            # print(f"Final state: {final_state}")
            # Let's comment out the final state print for now as it might change
            # Removed the extra pass and duplicated final_state print

        print("Finished graph execution!")
        return StreamingResponse(event_stream(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
