# graph.py
from typing import TypedDict, Annotated, Union, Sequence
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.messages import BaseMessage, ToolMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
import json
import operator
from langgraph.prebuilt import ToolNode

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    agent_outcome: Union[AgentAction, AgentFinish, None]
    return_direct: bool
    intermediate_steps: Annotated[list[tuple[AgentAction, str]], operator.add]

def create_agent_graph(llm, tools, prompt, checkpointer=None):
    # Define nodes
    async def call_model(state: AgentState, config: RunnableConfig):
        print(state)
        # Use the provided prompt template
        inputs = prompt + state["messages"]
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
        last_msg = state["messages"][-1]
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