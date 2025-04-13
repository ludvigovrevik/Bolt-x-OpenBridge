# Create server parameters for stdio connection
from dotenv import load_dotenv
import os
## For running asyncio
load_dotenv()
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
## model for agent
model = ChatOpenAI(model="gpt-4o-mini")

## server parameters
server_params={
        "math": {
            "command": "python",
            # Make sure to update to the full absolute path to your math_server.py file
            "args": ["/home/teodorrk/projects/openbridge-mvp/teodor/langchain_mcp/math_server.py"],
            "transport": "stdio",
        },
        "weather": {
            "command": "python",
            # Make sure to update to the full absolute path to your weather_server.py file
            "args": ["/home/teodorrk/projects/openbridge-mvp/teodor/langchain_mcp/weather_server.py"],
            "transport": "stdio",
        }
    }

#print(server_params)

async def main(query: str):
    async with MultiServerMCPClient(server_params) as client:
        agent = create_react_agent(model, client.get_tools())
        response = await agent.ainvoke({"messages": query})

    return response

# Run the async main function - queries for testing
query = "what is the weather in st. louis, MO now?"
# query = "A factory produces 250 gadgets per day. If production increases by 20 gadgets each day for 5 days, how many gadgets will the factory produce in total over those 5 days?"
# query = "What is (3+5) * 4 - 13"

if __name__ == "__main__":
    response=asyncio.run(main(query))
    print('------------')
    print(response)