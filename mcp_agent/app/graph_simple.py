from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
import os
from .load_model import load_model
from langchain_core.messages import (
    BaseMessage, HumanMessage, AIMessage, SystemMessage
)
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union, Sequence
from typing_extensions import Annotated
import operator
from .prompts.creator_prompt import get_unified_creator_prompt
from langgraph.prebuilt.chat_agent_executor import AgentState
from .utils.artifact_functions import get_artifact_files, artifact_exists
import logging
from .prompt import get_prompt

logger = logging.getLogger(__name__)


class MyAgentState(AgentState):
    """State of the agent with dynamic file loading."""
    cwd: str = Field(default=".", description="Current working directory")
    model_name: str = ""
    test_mode: bool = False
    use_planner: bool = False
    step_count: int = 0
    max_steps: int = 1
    files: Optional[List[str]] = None  # Changed to List[str] for file paths
    ui_components: Optional[List[Dict[str, Any]]] = None  # Fixed typo: ui_compponents -> ui_components
    artifact_id: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True

    def get_current_files(self) -> List[str]:
        """Get files from the artifact, loading them if needed."""
        # If we have an artifact_id but no files loaded, load them
        if self.get("artifact_id") and not self.get("files"):
            try:
                if artifact_exists(self.get("artifact_id")):
                    files = get_artifact_files(self.get("artifact_id"))
                    # Update the state with loaded files
                    self["files"] = files
                    logger.info(f"Loaded {len(files)} files for artifact {self.get('artifact_id')}")
                else:
                    logger.warning(f"Artifact {self.get('artifact_id')} not found")
                    self["files"] = []
            except Exception as e:
                logger.error(f"Failed to load files for artifact {self.get('artifact_id')}: {e}")
                self["files"] = []
        
        return self.get("files", [])


def create_agent_prompt(state: MyAgentState) -> List[BaseMessage]:
    """Create the prompt for the agent based on the current state."""
    # Fix: Use dict-style access for TypedDict
    cwd = state.get("cwd", ".")
    user_request = state["messages"][-1] if state.get("messages") else HumanMessage(content="")

    files = state.get("files", [])
    
    ui_components = state.get("ui_components", [])
    artifact_id = state.get("artifact_id")
    
    system_msg = get_unified_creator_prompt(
        cwd=cwd,
        user_request=user_request.content,
        files=files,
        ui_components=ui_components,
        artifact_id=artifact_id
    )
    
    # Return BaseMessage objects
    prompt = [SystemMessage(content=system_msg)] + state["messages"]
    logger.info(f"Invoking agent with prompt: {prompt}")
    return prompt


def create_agent_graph(tools: Optional[List[Any]] = None) -> Any:
    """Create a React agent with the given model and tools."""
    if tools is None:
        tools = []

    model = load_model(model_name="gpt-4.1-nano")

    return create_react_agent(
        model=model,
        tools=tools,
        prompt=get_prompt(),
        state_schema=MyAgentState,
    )