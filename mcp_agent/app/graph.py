# graph.py
from typing import TypedDict, Annotated, Union, Sequence
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.messages import BaseMessage, ToolMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from .load_model import load_model
import json
import operator
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

class AgentState(BaseModel):
    """State of the agent."""
    cwd: str = Field(default=".", description="Current working directory")
    messages: Annotated[Sequence[BaseMessage], operator.add]
    agent_outcome: Union[AgentAction, AgentFinish, None] = None
    return_direct: bool = False
    intermediate_steps: Annotated[list[tuple[AgentAction, str]], operator.add]  = Field(default_factory=list)
    model_name : str = "gpt-4o"  # Default model name

def create_agent_graph(tools, prompt, checkpointer=None):
    # Define nodes
    async def call_model(state: AgentState, config: RunnableConfig):
        # Use the provided prompt template
        inputs = prompt + state.messages
        llm = load_model(model_name=state.model_name, tools=tools)
        response = await llm.ainvoke(inputs, config=config)
        return {"messages": [response]}

    # Define workflow
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)

    tool_node = ToolNode(tools)
    workflow.add_node("tools", tool_node)
    workflow.set_entry_point("agent")

    # Conditional edges
    def should_continue(state: AgentState):
        last_msg = state.messages[-1]
        if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
            return "continue"
        return "end"

    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"continue": "tools", "end": END}
    )

    workflow.add_edge("tools", "agent")
    if checkpointer:
        return workflow.compile(checkpointer)

    return workflow.compile()