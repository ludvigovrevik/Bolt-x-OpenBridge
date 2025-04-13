import smithery
import mcp
from langchain_core.tools import Tool
from langchain_experimental.utilities import PythonREPL
import os 
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
SMITHERY_API_KEY = os.getenv("SMITHERY_API_KEY")

# install smithery, langchain_mcp_tools
import smithery
import mcp
from langchain_mcp_tools import convert_mcp_to_langchain_tools
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
import asyncio

# MCP To LangChain Tools Conversion Utility, install langchain_mcp_tools
# https://pypi.org/project/langchain-mcp-tools/ 

# login to Smithery: https://smithery.ai/
# create a API Key
llm = ChatOpenAI(model="gpt-4o")

from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()

mcp_servers = {
    "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]
    },
}

async def print_stream(stream):
    """A utility to pretty print the stream."""
    async for s in stream:
        message = s["messages"][-1]
        if isinstance(message, tuple):
            print(message)
        else:
            message.pretty_print()

if __name__ == "__main__":
    async def main():
        try:
            tools, cleanup = await convert_mcp_to_langchain_tools(mcp_servers)
#            print(f"Available tools: {', '.join([t.name for t in tools])}")

            file_agent = create_react_agent(llm, tools, checkpointer=memory)
            
            message = "Can you read the contents of my directory? Which files are there?"
            inputs = {"messages": [HumanMessage(content=message)]}
            config = {"configurable": {"thread_id": "42"}}
            await print_stream(file_agent.astream(inputs, config, stream_mode="values"))
            
        finally:
            await cleanup()

    asyncio.run(main())
    
# message = "Can you read the contents of the file 'test.py'? It is in this directory use ./test.py as path."
# agent_response = await file_agent.ainvoke({"messages": message})
# agent_response