# Browser Automation Agent

This project demonstrates a coding agent connected to ExecuteAutomation's Playwright MCP server for browser automation tasks.

## Setup

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Install the ExecuteAutomation Playwright MCP server:

```bash
npm install -g @executeautomation/playwright-mcp-server
```

## Components

- `browser_agent.py`: FastAgent implementation that connects to the Playwright MCP server
- `fastagent.config.yaml`: Configuration file for the FastAgent that includes the Playwright MCP server configuration

## Usage

Run the browser agent:

```bash
python browser_agent.py
```

This will start an interactive session where you can communicate with the agent to perform browser automation tasks.

### Example Commands

```
Navigate to https://www.google.com
```

```
Fill the search box with "FastAgent MCP" and click the search button
```

```
Take a screenshot of the current page
```

```
Extract all the visible text from the current page
```

```
Close the browser
```

## Advanced Usage

You can modify the agent's behavior by:

1. Changing the agent's instructions in `browser_agent.py`
2. Integrating with other MCP servers in `fastagent.config.yaml`
3. Using the ExecuteAutomation Playwright MCP server's advanced features like code generation

## Troubleshooting

If you encounter issues:

1. Make sure all dependencies are installed
2. Verify that the ExecuteAutomation Playwright MCP server is installed correctly
3. Check the MCP server configuration in `fastagent.config.yaml`
4. Make sure you have Node.js installed for the Playwright MCP server to work
