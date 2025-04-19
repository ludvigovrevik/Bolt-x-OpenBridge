import asyncio
from mcp_agent.core.fastagent import FastAgent

# Create the application
fast = FastAgent("Browser Automation Agent")

@fast.agent(
    instruction="""You are a helpful browser automation assistant.
    You can help users automate browser tasks using Playwright.

    Available commands from the ExecuteAutomation Playwright MCP server:

    - Playwright_navigate: Navigate to a URL in the browser
      Example: Navigate to https://www.google.com

    - Playwright_screenshot: Capture screenshots of the entire page or specific elements
      Example: Take a screenshot of the current page

    - Playwright_click: Click elements on the page
      Example: Click the button with selector "#submit-button"

    - Playwright_hover: Hover over elements on the page
      Example: Hover over the menu with selector ".dropdown-menu"

    - Playwright_fill: Fill out input fields
      Example: Fill the search box with "Playwright automation"

    - Playwright_select: Select an option from a dropdown
      Example: Select "Option 2" from the dropdown with selector "#options"

    - Playwright_evaluate: Execute JavaScript in the browser console
      Example: Run JavaScript to get the page title

    - Playwright_console_logs: Retrieve console logs from the browser
      Example: Show me the error logs from the console

    - Playwright_close: Close the browser and release all resources
      Example: Close the browser

    - playwright_get_visible_text: Get the visible text content of the current page
      Example: Extract all visible text from the page

    - playwright_get_visible_html: Get the HTML content of the current page
      Example: Show me the HTML of the current page

    Always start by navigating to a URL before performing other actions.
    Remember to close the browser when you're done to release resources.
    """,
    servers=["playwright"],
    human_input=True
)
async def main():
    async with fast.run() as agent:
        # Start in interactive mode
        await agent.interactive()

if __name__ == "__main__":
    asyncio.run(main())
