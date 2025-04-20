# graph.py
from typing import TypedDict, Annotated, Union, Sequence, List, Any
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.messages import BaseMessage, ToolMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from .load_model import load_model
import json
import operator
# Removed logging import
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage, HumanMessage, BaseMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_core.agents import AgentAction
from pydantic import BaseModel, Field
from .prompt import get_prompt, openbridge_example
from langgraph.prebuilt import create_react_agent
from .prompts.designer_prompt import get_designer_prompt
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import logging
from typing import List, Dict, Any, Optional, Tuple
import json
import logging
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_core.agents import AgentAction

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("agent_graph")

class AgentState(BaseModel):
    """State of the agent."""
    cwd: str = Field(default=".", description="Current working directory")
    messages: Annotated[Sequence[BaseMessage], operator.add]
    agent_outcome: Union[AgentAction, AgentFinish, None] = None
    return_direct: bool = False
    intermediate_steps: Annotated[list[tuple[AgentAction, str]], operator.add]  = Field(default_factory=list)
    model_name : str = "gpt-4.1"  # Default model name

    class Config:
        arbitrary_types_allowed = True


def create_agent_graph(tools, checkpointer=None):
    """Create a more efficient LangGraph REACT agent with the latest features."""
    logger.info(f"Creating agent graph with {len(tools)} tools")

    @RunnableLambda
    async def call_model(state: AgentState, config: RunnableConfig):
        """Call the LLM with the current conversation state."""
        logger.info(f"Calling model {state.model_name} with {len(state.messages)} messages")
        system_message = SystemMessage(content=get_prompt(
            cwd=state.cwd,
            tools=tools,
            openbridge_example=openbridge_example,
        ))
        inputs = [system_message] + state.messages
        llm = load_model(model_name=state.model_name, tools=tools)
        response = await llm.ainvoke(inputs, config=config)
        
        # Return updated state with the response
        return {"messages": state.messages + [response]}

    @RunnableLambda
    async def process_tool_execution(state: AgentState):
        """Execute tools and track intermediate steps."""
        # Get the last message with tool calls
        last_message = state.messages[-1]
        if not (isinstance(last_message, AIMessage) and last_message.tool_calls):
            return state

        tool_call = last_message.tool_calls[0]
        tool_name = tool_call["name"]
        tool_input = tool_call["args"]
        
        # Log the tool execution
        logger.info(f"Executing tool: {tool_name} with input: {json.dumps(tool_input)[:100]}...")
        
        # Create tool node for this execution
        tool_node = ToolNode(
            tools=tools,
            handle_tool_errors=lambda exception, tool_call: (
                f"Error executing tool {tool_call.get('name')}: {str(exception)}"
            ),
        )
        
        # Execute the tool
        result = await tool_node.ainvoke(state)
        
        # Create the agent action record
        agent_action = AgentAction(
            tool=tool_name,
            tool_input=tool_input,
            log=last_message.content
        )
        
        # Get the tool message content
        tool_message = result["messages"][-1]
        
        # Add to intermediate steps
        new_steps = state.intermediate_steps + [(agent_action, tool_message.content)]
        
        logger.info(f"New intermediate steps: {len(new_steps)}")
        
        # Return updated state
        return {
            "messages": result["messages"],
            "intermediate_steps": new_steps
        }

    # Create the state graph
    workflow = StateGraph(AgentState)
    logger.info("Initializing state graph")
    
    # Add nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", process_tool_execution)
    
    # Set entry point
    workflow.set_entry_point("agent")
    
    # Define conditional edge routing
    def should_continue(state: AgentState) -> str:
        """Determine if we should continue with tools or end the conversation."""
        last_message = state.messages[-1]
        
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            logger.info("Decision: Agent requested tool execution")
            return "tools"
        else:
            logger.info("Decision: Agent completed task, ending workflow")
            return "end"
    
    # Connect nodes
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )
    workflow.add_edge("tools", "agent")
    
    logger.info("Graph structure defined and edges connected")
    
    # Compile the graph
    if checkpointer:
        logger.info("Compiling graph with checkpointer")
        return workflow.compile(checkpointer=checkpointer)
    
    logger.info("Compiling graph without checkpointer")
    return workflow.compile()