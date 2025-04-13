import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Weather")

## defing the tools
tools = [{
    "type": "function",
    "name": "get_weather",
    "description": "Get current temperature for provided coordinates in celsius.",
    "parameters": {
        "type": "object",
        "properties": {
            "latitude": {"type": "number"},
            "longitude": {"type": "number"}
        },
        "required": ["latitude", "longitude"],
        "additionalProperties": False
    },
    "strict": True
}]

@mcp.tool()
async def get_weather(latitude, longitude):
    """Get current temperature for provided coordinates (latitude and longitude) in celsius."""
    response = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m,wind_speed_10m&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m")
    data = response.json()
    res = {"temperature": data['current']['temperature_2m'], "unit":data['current_units']['temperature_2m']}
    return res

@mcp.tool()
async def get_coordinates(location: str):
    """Get the coordinates (latitude and longitude) for a given location. This will be needed to get the weather for the location."""
    return tools[0]

if __name__ == "__main__":
    mcp.run(transport="stdio")