from typing import TypedDict, Annotated, Union, Sequence, List, Any, Optional, Dict
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.messages import BaseMessage, ToolMessage, AIMessage, SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from .load_model import load_model
import json
import operator
from app.retriever.retriever import component_info_tool  # Import the new tool
from langgraph.prebuilt import ToolNode
from langchain_core.runnables import RunnableConfig, RunnableLambda
from pydantic import BaseModel, Field
import logging
import asyncio

# Import the test framework
from .test.test_framework import TestRunner

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("agent_graph")
from .prompt import get_test_prompt

class AgentState(BaseModel):
    """State of the agent."""
    cwd: str = Field(default=".", description="Current working directory")
    messages: Annotated[Sequence[BaseMessage], operator.add]
    agent_outcome: Union[AgentAction, AgentFinish, None] = None
    return_direct: bool = False
    intermediate_steps: Annotated[list[tuple[AgentAction, str]], operator.add] = Field(default_factory=list)
    model_name: str = "gpt-4.1"  # Default model name
    test: bool = False  # Flag to indicate if we're in test mode
    test_responses: Optional[List[Dict[str, Any]]] = None  # Predefined responses for testing
    system_prompt: Optional[str] = None  # Custom system prompt
    design_template: Optional[str] = None  # Design template as human message

    class Config:
        arbitrary_types_allowed = True


def create_agent_graph(
    tools, 
    system_prompt=None, 
    design_template=None,
    checkpointer=None
):
    """Create an async LangGraph REACT agent with customizable prompts and testing capabilities.
    
    Args:
        tools: List of available tools
        system_prompt: Optional custom system prompt for formatting instructions
        design_template: Optional design template as a human message
        checkpointer: Optional checkpointer for state persistence
        
    Returns:
        Compiled async StateGraph for the agent
    """
    logger.info(f"Creating agent graph with {len(tools)} tools")

    @RunnableLambda
    async def call_model(state: AgentState, config: RunnableConfig):
        """Call the LLM with the current conversation state."""
        logger.info(f"Calling model {state.model_name} with {len(state.messages)} messages")
        
        # Use custom system prompt if provided in state, fall back to parameter, then default
        # Import here to avoid circular imports
        from .prompt import get_prompt
        from .prompt import get_test_prompt
        system_content = get_test_prompt(
            cwd=state.cwd,
            tools=tools,
        )
        
        system_message = SystemMessage(content=system_content)
        
        # Initialize message list with system message
        inputs = [system_message]
        
        # Import designer prompt if needed
        from .prompts.designer_prompt import get_designer_prompt
        design_template = get_designer_prompt(
            cwd=state.cwd,
            file_list=[],
            prev_spec={},
        )
        design_msg = HumanMessage(content=design_template)
        
        inputs.append(design_msg)
    
        # Add existing conversation messages
        inputs.extend(state.messages)
        
        # If in test mode, use mock model instead of actual LLM
        if state.test and state.test_responses:
            from .test.test_framework import MockModel
            llm = MockModel(state.test_responses)
            logger.info("Using mock model for testing")
        else:
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
        
        # If in test mode and we have a mock tool response, use that instead
        if state.test and hasattr(state, 'mock_tool_responses') and tool_name in state.mock_tool_responses:
            # Create a mock tool message
            mock_result = state.mock_tool_responses[tool_name]
            tool_message = ToolMessage(content=mock_result, name=tool_name)
            result = {"messages": state.messages + [tool_message]}
            logger.info(f"Using mock tool response for {tool_name}")
        else:
            # Execute the tool normally
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