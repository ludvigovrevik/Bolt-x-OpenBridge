# graph.py
from typing import TypedDict, Annotated, Union, Sequence, Optional, Dict, List
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.messages import BaseMessage, ToolMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from .load_model import load_model
import json
import operator
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from .prompts import get_

class AgentState(BaseModel):
    """State of the agent."""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    agent_outcome: Union[AgentAction, AgentFinish, None] = None
    return_direct: bool = False
    intermediate_steps: Annotated[list[tuple[AgentAction, str]], operator.add]  = Field(default_factory=list)
    model_name : str = "gpt-4o"  # Default model name
    """Extended state with design specifications"""

class EnhancedAgentState(AgentState):
    """Extended state with design specifications"""
    design_spec: Optional[DesignSpecification] = None
    current_files: Dict[str, str] = Field(default_factory=dict)
    implementation_plan: List[str] = Field(default_factory=list)

def create_agent_graph(llm, tools, prompt=DESIGNER_PROMPT, checkpointer=None):
    workflow = StateGraph(EnhancedAgentState)
    
    # Design-specific nodes
    async def design_analyst(state: EnhancedAgentState, config: RunnableConfig):
        # Enhance user prompt with design thinking
        enhanced = await llm.ainvoke({
            "user_query": state.messages[-1].content,
            "system_constraints": DESIGN_CONSTRAINTS,
            "existing_files": state.current_files
        })
        return {"messages": [AIMessage(content=enhanced)]}

    async def spec_generator(state: EnhancedAgentState, config: RunnableConfig):
        # Generate structured design spec
        spec = await llm.ainvoke({
            "messages": state.messages,
            "template": DESIGNER_PROMPT
        })
        return {"design_spec": DesignSpecification(**json.loads(spec.content))}

    # Modified workflow
    workflow.add_node("design_analyst", design_analyst)
    workflow.add_node("spec_generator", spec_generator)
    workflow.add_node("agent", call_model)  # Original agent node
    workflow.add_node("tools", tool_node)

    workflow.set_entry_point("design_analyst")
    workflow.add_edge("design_analyst", "spec_generator")
    workflow.add_edge("spec_generator", "agent")
    
    # Conditional tool usage after agent
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"continue": "tools", "end": END}
    )
    workflow.add_edge("tools", "agent")

    return workflow.compile(checkpointer=checkpointer)