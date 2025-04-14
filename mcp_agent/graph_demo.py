"""
Script Name: graph_demo.py
Author: Robotic Socialism
Date: January 21, 2024
Description: This examples builds off the base chat executor. 
It is highly recommended you learn about that executor before going through this script. 
You can find documentation for that example in official langgraph github.

"""

from langgraph.graph import StateGraph, END
from langgraph.prebuilt.tool_executor import ToolExecutor
from langchain_core.messages import BaseMessage
from typing import TypedDict, Annotated, Union, List, Tuple
from langchain_core.agents import AgentAction, AgentFinish, AgentActionMessageLog
import operator

class AgentState(TypedDict):
    input: str
    chat_history: list[BaseMessage]
    agent_outcome: Union[AgentAction, AgentFinish, None]
    intermediate_steps: Annotated[list[tuple[AgentAction, str]], operator.add]

class MCPAgent:
    def __init__(self, llm):
        self.llm = llm
        self.mcp_servers = {
            "filesystem": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-filesystem", os.getcwd()]
            }
        }
        self.tools = None
        self.tool_executor = None # Initialize ToolExecutor
        self.prompt = self.create_prompt(os.getcwd())
        self.checkpointer = MemorySaver()
        self.workflow = None # Initialize LangGraph workflow

    async def initialize(self):
        self.tools, self.cleanup_func = await convert_mcp_to_langchain_tools(self.mcp_servers)
        if self.tools:
            self.tool_executor = ToolExecutor(self.tools) # Initialize ToolExecutor here
            self.workflow = self._create_langgraph_workflow() # Create the LangGraph workflow
        else:
            raise Exception("No tools were loaded from MCP servers")

    def create_prompt(self, cwd: str) -> ChatPromptTemplate:
        system_message = f"""You are an AI assistant working with files in {cwd}..."""
        return ChatPromptTemplate.from_template(
            f"""{system_message}

            Answer questions using these rules:
            1. Use XML formatting for file listings
            2. Follow ID patterns for artifacts

            Tools available:
            {{tools}}

            Use format:
            Question: {{input}}
            Thought:{{agent_scratchpad}}
            """
        )

    # --- LangGraph Specific Methods ---

    def _run_agent(self, state):
        """Invokes the LLM with the ReAct prompt."""
        inputs = state.copy()
        return {"agent_outcome": self.prompt.invoke(inputs) | self.llm}

    def _execute_tools(self, state):
        """Executes the tool chosen by the agent."""
        last_message = state['agent_outcome']
        tool_name = last_message.tool
        tool_input = last_message.tool_input

        action = ToolInvocation(
            tool=tool_name,
            tool_input=tool_input,
        )
        response = self.tool_executor.invoke(action)
        return {"intermediate_steps": [(state['agent_outcome'], response)]}

    def _should_continue(self, state):
        """Determines if the agent should continue or finish."""
        last_message = state['agent_outcome']
        if isinstance(last_message, AgentFinish):
            return "end"
        elif isinstance(last_message, AgentActionMessageLog):
            return "continue"
        else:
            return "continue" # Default to continue if unsure

    def _create_langgraph_workflow(self):
        """Creates the LangGraph workflow."""
        builder = StateGraph(AgentState)

        builder.add_node("agent", self._run_agent)
        builder.add_node("action", self._execute_tools)

        builder.set_entry_point("agent")

        builder.add_conditional_edges(
            "agent",
            self._should_continue,
            {"continue": "action", "end": END},
        )

        builder.add_edge("action", "agent")

        return builder.compile()

    async def astream_events(self, query: str, config: dict):
        if not self.workflow:
            raise Exception("LangGraph workflow not initialized. Call initialize() first.")

        inputs = {"input": query, "chat_history": [], "intermediate_steps": []}

        async for event in self.workflow.astream(inputs, config=config):
            yield event # You might need to adapt the output format to match the previous one

    async def format_response(self, content: str) -> str:
        """Ensure proper XML tag formatting in model responses"""
        content = content.replace("<boltArtifact", "\n<boltArtifact")
        content = content.replace("</boltArtifact>", "</boltArtifact>\n")
        return content