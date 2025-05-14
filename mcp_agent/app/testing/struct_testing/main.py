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
    create_agent_graph as create_reasoning_agent_graph,
    )
from .graph import create_agent_graph, AgentState, BoltArtifact
from .prompt import openbridge_example
#from .prompt import get_prompt
import logging # Add logging import
import uuid

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConfigLLM(BaseModel):
    model_name: str = os.getenv("LLM_MODEL_NAME", "gpt-4.1-nano")
    temperature: float = 0.0

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
            }
        self.tools = None
        self.cleanup_func = None
        self.config = {"configurable": {
            "thread_id": uuid.uuid4(),
            "parser": BoltArtifact,
        }}
        self.output_parser = None   # Placeholder for output parser
        self.human_in_the_loop = False
        self.prompt = None
        self.graph = None
        self.checkpointer = MemorySaver()
        self.reasoning_agent = None
        self.structured_output = False
        self.initialized = False
        self.action_extractor = None  # Will be initialized when needed
        self.test_mode = False
    
    async def set_agent_type(self, reasoning: bool = False):
        """Set the agent type and reinitialize the graph if needed"""
        # Store the requested reasoning mode but ALWAYS use standard agent
        self.reasoning_agent = reasoning
        
        logger.info(f"Agent set to standard type (reasoning preference noted: {reasoning})")
        
        # Only rebuild graph if we've already initialized and there was a change
        if self.initialized and self.tools and self.graph is None:
            logger.info("Building standard agent graph")
            
            # Always use the standard agent graph regardless of reasoning setting
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
            
            # Always use the standard agent graph
            self.graph = create_agent_graph(
                self.tools,
                self.checkpointer
            )
        else:
            raise Exception("No tools were loaded from MCP servers")

    def create_prompt(self, cwd: str) -> ChatPromptTemplate:
        return [SystemMessage(content=get_prompt(cwd, self.tools))]

    def get_action_extractor(self):
        """Get or create a StreamingActionExtractor instance."""
        if self.action_extractor is None:
            from .utils.StreamingActionExtractor import StreamingActionExtractor
            self.action_extractor = StreamingActionExtractor()
        return self.action_extractor

    # Add output formatting middleware
    async def format_response(self, content): # Removed type hint for flexibility
        """Ensure proper XML tag formatting in model responses"""
        if isinstance(content, str): # Check if content is a string
            content = content.replace("<boltArtifact", "\n<boltArtifact")
            content = content.replace("</boltArtifact>", "</boltArtifact>\n")
        # If not a string, return content as is
        return content

    async def astream_events(self, input: List[BaseMessage], config: dict):
        initial_state = AgentState(
            cwd=os.getcwd(),
            model_name=self.llm.model_name,
            messages=input,
            use_planner=self.reasoning_agent,
            test_mode=self.test_mode,
        )
        print(f"Using standard agent graph")
        
        async for event in self.graph.astream_events(
            initial_state,
            config=self.config,
            stream_mode="values"
        ):
            if initial_state.test_mode:
                if event["event"] == "on_chain_stream":
                    # Handle the event from the chain
                    chunk = event["data"]["chunk"]
                    
                    # If chunk is a dictionary with bolt_artifact (your case)
                    if isinstance(chunk, dict) and "bolt_artifact" in chunk:
                        bolt_artifact = chunk["bolt_artifact"]
                        if isinstance(bolt_artifact, AIMessage):
                            print(f"Raw chunk content: {bolt_artifact.content}")  # Debug log for raw content
                            chunk_content = await self.format_response(bolt_artifact.content)
                            yield chunk_content
                        
            #response = ""
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                chunk_content = await self.format_response(chunk.content)
                print(chunk_content)
                yield chunk.content

    async def stream_xml_content(self, input: List[BaseMessage], config: Optional[dict] = None):
        """Stream XML-formatted content with boltArtifact and boltAction tags."""
        config = config or self.config
        print(f"Using standard agent graph without structured output")
        
        async for content in self.astream_events(input=input, config=config):
            # Focus ONLY on the event carrying content chunks from the LLM stream
            logger.debug(f"Raw chunk content: {content}")  # Debug log for raw content

            # Just send the content without any processing
            # The frontend will handle the XML parsing
            if content:
                yield content

    async def stream_artifacts(self, input: List[BaseMessage], config: Optional[dict] = None):
        """Stream and extract artifacts from agent outputs."""
        import uuid
        
        extractor = self.get_action_extractor()
        config = config or self.config
        artifact_started = False
        buffered_actions = []  # Buffer to hold actions until we have artifact info
        
        async for content in self.astream_events(input=input, config=config):
            # Process the chunk content with the extractor
            new_actions = extractor.feed(content)
            
            # If we have actions but no artifact info yet, buffer them
            if new_actions and not extractor.artifact_info and not artifact_started:
                buffered_actions.extend(new_actions)
                continue
                
            # If we have artifact info and haven't started the artifact, emit the opening tag
            if extractor.artifact_info and not artifact_started:
                aid = extractor.artifact_info["id"]
                title = extractor.artifact_info["title"]
                print(f"Artifact ID: {aid}, Title: {title}")
                artifact_started = True
                yield f'<boltArtifact id="{aid}" title="{title}">'
                
                # Emit any buffered actions
                for action in buffered_actions:
                    if action["type"] == "shell":
                        yield f'<boltAction type="shell">{action["command"]}</boltAction>'
                    elif action["type"] == "file":
                        path = action["file_path"]
                        content = action["content"]
                        yield f'<boltAction type="file" filePath="{path}">{content}</boltAction>'
                    elif action["type"] == "message":
                        yield f'{action["content"]}'
                buffered_actions = []  # Clear the buffer
            
            # Emit any new actions if we've started the artifact
            if artifact_started:
                for action in new_actions:
                    if action["type"] == "shell":
                        yield f'<boltAction type="shell">{action["command"]}</boltAction>'
                    elif action["type"] == "file":
                        path = action["file_path"]
                        content = action["content"]
                        yield f'<boltAction type="file" filePath="{path}">{content}</boltAction>'
                    elif action["type"] == "message":
                        yield f'{action["content"]}'
        
        # If we have buffered actions but never got artifact info, create a default artifact
        if buffered_actions and not artifact_started:
            default_id = f"generated-artifact-{uuid.uuid4()}"
            default_title = "Generated Output"
            print(f"Using default artifact - ID: {default_id}, Title: {default_title}")
            yield f'<boltArtifact id="{default_id}" title="{default_title}">'
            
            # Emit the buffered actions
            for action in buffered_actions:
                if action["type"] == "shell":
                    yield f'<boltAction type="shell">{action["command"]}</boltAction>'
                elif action["type"] == "file":
                    path = action["file_path"]
                    content = action["content"]
                    yield f'<boltAction type="file" filePath="{path}">{content}</boltAction>'
                elif action["type"] == "message":
                    yield f'{action["content"]}'
            
            artifact_started = True
        
        # Close the artifact tag if we opened one
        if artifact_started:
            yield '</boltArtifact>'

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
            if app.state.agent.structured_output:
                async for content in app.state.agent.stream_artifacts(
                    input=langchain_messages,
                ):
                    
                    # Direct yield without additional processing
                    yield content
            else:
                async for content in app.state.agent.stream_xml_content(
                    input=langchain_messages,
                ):
                    
                    # Direct yield without additional processing
                    yield content
                    
        print("Finished graph execution!")
        return StreamingResponse(event_stream(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
