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
from .graph_simple import create_agent_graph as create_react_agent, MyAgentState
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
        self.tools = []  # Initialize tools as an empty list
        self.cleanup_func = None
        self.config = {"configurable": {
            "thread_id": uuid.UUID,
        }}
        # Initialize agent state as instance variable
        self.agent_state = MyAgentState(
            cwd=os.getcwd(),
            model_name=self.llm.model_name,
            messages=[],
            test_mode=False,
            use_planner=False,
            artifact_id=None,
            files=None,
            ui_components=None
        )
        
        self.output_parser = None   # Placeholder for output parser
        self.human_in_the_loop = False
        self.prompt = None
        self.graph = None
        self.initialized = False
        self.action_extractor = None  # Will be initialized when needed
    
    def update_agent_state(self, **kwargs):
        """Enhanced update method that handles all agent state changes"""
        for key, value in kwargs.items():
            if key in self.agent_state or hasattr(self.agent_state, key):
                self.agent_state[key] = value
                logger.info(f"Updated agent state: {key} = {value}")
            else:
                logger.warning(f"Unknown agent state key: {key}")
        
        # Handle reasoning mode update
        if 'use_planner' in kwargs:
            logger.info(f"Agent reasoning mode set to: {kwargs['use_planner']}")
        
        # Handle test mode update
        if 'test_mode' in kwargs:
            logger.info(f"Agent test mode set to: {kwargs['test_mode']}")

    def get_agent_state(self) -> MyAgentState:
        """Get the current agent state"""
        return self.agent_state

    def set_artifact(self, artifact_id: str, files: Optional[List[str]] = None):
        """Convenience method to set artifact using update_agent_state"""
        update_data = {"artifact_id": artifact_id}
        if files:
            update_data["files"] = files
        
        self.update_agent_state(**update_data)

    def set_reasoning_mode(self, reasoning: bool):
        """Convenience method to set reasoning mode using update_agent_state"""
        self.update_agent_state(use_planner=reasoning)

    def set_test_mode(self, test_mode: bool):
        """Convenience method to set test mode using update_agent_state"""
        self.update_agent_state(test_mode=test_mode)

    async def initialize(self):
        mcp_tools, self.cleanup_func = await convert_mcp_to_langchain_tools(self.mcp_servers)
        self.tools.extend(mcp_tools)

        if self.tools:
            print("MCP tools loaded successfully")
        
        self.initialized = True
        
        # Always use the standard agent graph
        self.graph = create_react_agent(tools=self.tools)

    def get_action_extractor(self):
        """Get or create a StreamingActionExtractor instance."""
        if self.action_extractor is None:
            from .utils.StreamingActionExtractor import StreamingActionExtractor
            self.action_extractor = StreamingActionExtractor()
        return self.action_extractor

    async def astream_events(self, input: List[BaseMessage], config: dict):
        # Update the persistent agent state with new messages
        self.agent_state["messages"] = input
        
        files = self.agent_state.get('files') or []
        logger.info(f"Using agent state: artifact_id={self.agent_state.get('artifact_id')}, files={len(files)}")
        content = ""
        async for event in self.graph.astream_events(
            self.agent_state,  # Use the persistent state
            config=self.config,
            stream_mode="values"
        ):
            if self.agent_state.get("test_mode"):
                if event["event"] == "on_chain_stream":
                    chunk = event["data"]["chunk"]
                    if isinstance(chunk, dict) and "bolt_artifact" in chunk:
                        bolt_artifact = chunk["bolt_artifact"]
                        if isinstance(bolt_artifact, AIMessage):
                            logger.debug(f"Raw chunk content: {bolt_artifact.content}")
                            yield bolt_artifact.content
                        
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.tool_calls:
                    logger.print(f"Tool call detected: {chunk.tool_calls}")
                content += chunk.content
                yield chunk.content

    async def stream_xml_content(self, input: List[BaseMessage], config: Optional[dict] = None):
        """
        Enhanced streaming with agent state management.
        This is now the single point of truth for streaming responses.
        """
        config = config or self.config
        
        # Update agent state with incoming messages
        self.agent_state["messages"] = input
        

        files = self.agent_state.get('files') or []
        logger.info(f"Streaming with artifact_id: {self.agent_state.get('artifact_id')}, files: {len(files)}")
        logger.debug(f"Agent state summary: {self.get_state_summary()}")
        
        async for content in self.astream_events(input=input, config=config):
            logger.debug(f"Streaming content chunk: {content[:100]}...")
            
            # Direct yield - let the frontend handle XML parsing
            if content:
                yield content

    def get_state_summary(self) -> Dict[str, Any]:
        """Get a summary of current agent state for debugging"""
        return {
            "artifact_id": self.agent_state.get("artifact_id"),
            "files_count": len(self.agent_state.get("files") or []),
            "has_messages": bool(self.agent_state.get("messages")),
            "reasoning_mode": self.agent_state.get("use_planner", False),
            "test_mode": self.agent_state.get("test_mode", False),
            "cwd": self.agent_state.get("cwd")
        }

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
        self.initialized = False