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
from pydantic import BaseModel
from typing import List, Dict, Any, Optional # Added Any, Optional
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    HumanMessage, AIMessage, SystemMessage, BaseMessage)
import asyncio
from langchain_mcp_tools import convert_mcp_to_langchain_tools
from langgraph.checkpoint.memory import MemorySaver
import json
from langchain_core.prompts import ChatPromptTemplate
from .load_model import load_model
#from .graph import create_agent_graph, AgentState

from .graph import create_agent_graph, AgentState
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
            #"filesystem": {
            #    "command": "npx",
            #    "args": [
            #        "-y",  # Crucial for non-interactive execution
            #        "@modelcontextprotocol/server-filesystem",
            #        os.path.expanduser(self.repo_root)  # Home directory as root
            #    ],
            #    "cwd": os.path.expanduser(self.repo_root)  # Explicit working directory
            #},
            #"mcp-figma": {
            #    "command": "npx",
            #    "args": [
            #        "-y",
            #        "mcp-figma"
            #    ]
            #},
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
        self.config = {"configurable": {
            "thread_id": uuid.uuid4(),
        }}
        self.output_parser = None   # Placeholder for output parser
        self.human_in_the_loop = False
        self.prompt = None
        self.graph = None
        self.reasoning_agent = None
        self.initialized = False
        self.action_extractor = None  # Will be initialized when needed
        self.test_mode = False
    
    async def set_agent_type(self, reasoning: bool = False):
        """Set the agent type and reinitialize the graph if needed"""
        # Store the requested reasoning mode but ALWAYS use standard agent
        self.reasoning_agent = reasoning
        
        logger.info(f"Agent set to standard type (reasoning preference noted: {reasoning})")
        
        return self.reasoning_agent

    async def initialize(self):
        self.tools, self.cleanup_func = await convert_mcp_to_langchain_tools(self.mcp_servers)
        
        if self.tools:
            print("MCP tools loaded successfully")
        
        self.initialized = True  # Set flag to True after successful initialization
        
        # Always use the standard agent graph
        self.graph = create_agent_graph(
            tools=self.tools,
        )

    from .prompt import get_prompt
    def create_prompt(self, cwd: str) -> ChatPromptTemplate:
        return [SystemMessage(content=get_prompt(cwd, self.tools))]

    def get_action_extractor(self):
        """Get or create a StreamingActionExtractor instance."""
        if self.action_extractor is None:
            from .utils.StreamingActionExtractor import StreamingActionExtractor
            self.action_extractor = StreamingActionExtractor()
        return self.action_extractor

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
                            yield bolt_artifact.content
                        
            #response = ""
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
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