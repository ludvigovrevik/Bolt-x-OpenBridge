# mcp_use.py

###################################################################
# MCP Agent for LangChain

# https://github.com/hideya/langchain-mcp-tools-py?tab=readme-ov-file

####################################################################

import os
import asyncio
from contextlib import asynccontextmanager, AsyncExitStack
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_mcp_tools import convert_mcp_to_langchain_tools
from langgraph.checkpoint.memory import MemorySaver

class MCPAgent:
    def __init__(self, llm, checkpointer=None):
        self.llm = llm
        self.checkpointer = checkpointer or MemorySaver()
        self.mcp_servers = {
            "filesystem": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-filesystem", os.getcwd()]
            }
        }
        self.tools = None
        self.agent = None
        self.lock = asyncio.Lock()

    @asynccontextmanager
    async def server_context(self):
        async with self.lock:
            async with AsyncExitStack() as stack:
                # Get tools and cleanup manager
                self.tools, cleanup = await convert_mcp_to_langchain_tools(self.mcp_servers)
                
                # Wrap cleanup to accept exception arguments
                async def wrapped_cleanup(exc_type, exc, tb):
                    await cleanup()
                
                # Register cleanup with exception handling
                stack.push_async_exit(wrapped_cleanup)
                
                # Create agent
                self.agent = create_react_agent(self.llm, self.tools, checkpointer=self.checkpointer)
                yield self

    async def astream(self, messages, thread_id="default"):
        """Async generator for streaming agent responses"""
        async with self.server_context() as agent:
            inputs = {"messages": messages}
            config = {"configurable": {"thread_id": thread_id}}
            
            async for chunk in self.agent.astream(inputs, config, stream_mode="values"):
                message = chunk["messages"][-1]
                if hasattr(message, 'content'):
                    yield {"text": message.content, "inArtifact": False}
                elif hasattr(message, 'additional_kwargs'):
                    yield {"text": str(message.additional_kwargs), "inArtifact": True}