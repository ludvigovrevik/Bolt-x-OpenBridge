###################################################################
# Dette er en demo av hvordan vi kan bruke MCP agent i langchain

# Dette er source code for use MCP agenten som jeg brukte som base
# https://github.com/mcp-use/mcp-use/blob/main/mcp_use/agents/mcpagent.py

# MCP Agent for LangChain
# Dette er source code for å gjøre MCP til langchain tools
# https://github.com/hideya/langchain-mcp-tools-py?tab=readme-ov-file

# further on this is one way we can create more complex systems
# https://github.com/roboticsocialism/langgraph_demo/blob/main/langgraph_demo.py

# This is how we can create human in the loop using the standard scrathpad agent
# https://langchain-ai.github.io/langgraph/how-tos/create-react-agent-hitl/#code

####################################################################

# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional # Added Any, Optional
from typing import Dict, Optional
from datetime import datetime
import os
from dotenv import load_dotenv
from langchain_core.messages import (
    HumanMessage, AIMessage, SystemMessage, BaseMessage)
import asyncio
from .utils.artifact_functions import save_artifact_to_file


import logging # Add logging import
import uuid

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from .models.artifact_models import (
    SavedArtifact, 
    ArtifactMetadata, 
    ProjectInfo,
    FilesRequest, 
    FileItem, 
    ChatMessage, 
    MessageData,
    ChatRequest,
    FileData,
    ChatRequest,
    ArtifactSummary,
    ArtifactFilesResponse,
    FileContentResponse
)



from .mcp_agent import MCPAgent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


from .vector_store.tools.retrieve_files import retrieve_files
from .vector_store.tools.retrieve_file_contents import retrieve_file_contents
from .vector_store.tools.get_specific_file_content import get_specific_file_content
from .vector_store.tools.search_all_artifacts_for_content import search_all_artifacts_for_content
from .vector_store.tools.search_code_patterns import search_code_patterns

vs_store_tools = [
    retrieve_files,
    retrieve_file_contents,
    get_specific_file_content,
    search_all_artifacts_for_content,
    search_code_patterns
]

@app.on_event("startup")
async def startup_event():
    app.state.agent = MCPAgent()
    await app.state.agent.initialize() # Initialize the agent
    # Additional setup if needed
    app.state.agent.tools.extend(vs_store_tools)  # Add vector store tools to agent
    logger.info(f"Agent initialized with tools: {app.state.agent.tools}")
    print("Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state.agent, 'cleanup'):
        await app.state.agent.cleanup()
    # Additional cleanup if needed
    print("Application shutdown complete")


@app.post("/api/files")
async def receive_files(request: FilesRequest):
    logger.info(f"=== RECEIVED FILES REQUEST ===")
    logger.info(f"Artifact ID: {request.artifact_id}")
    logger.info(f"Message ID: {request.message_id}")
    logger.info(f"Chat ID: {request.chat_id}")
    logger.info(f"URL ID: {request.url_id}")
    logger.info(f"Application: {request.application_name}")
    logger.info(f"Thread ID: {request.thread_id}")
    logger.info(f"Files count: {len(request.files)}")
    logger.info(f"Messages count: {len(request.messages) if request.messages else 0}")
    
    # Extract file paths for agent state
    file_paths = [file.path for file in request.files]
    
    # Update agent state with artifact info using the unified method
    artifact_id = request.artifact_id
    if artifact_id:
        app.state.agent.update_agent_state(
            artifact_id=artifact_id,
            files=file_paths
        )
        logger.info(f"Updated agent state with artifact_id: {artifact_id} and {len(file_paths)} files")
    
    # Categorize files
    text_files = [f for f in request.files if not f.is_binary]
    binary_files = [f for f in request.files if f.is_binary]
    
    logger.info(f"Text files: {len(text_files)}, Binary files: {len(binary_files)}")
    
    # Log file details (first 5 files)
    for i, file in enumerate(request.files[:5]):
        logger.info(f"File {i+1}: {file.path} ({'binary' if file.is_binary else 'text'}, {file.size} bytes)")
    
    if len(request.files) > 5:
        logger.info(f"... and {len(request.files) - 5} more files")
    
    # Save artifact to JSON file
    try:
        saved_file_path = save_artifact_to_file(request)
        logger.info(f"Artifact successfully saved to: {saved_file_path}")
    except Exception as e:
        logger.error(f"Failed to save artifact: {e}")
        saved_file_path = None
    
    return {
        "success": True,
        "artifact_id": request.artifact_id,
        "chat_id": request.chat_id,
        "url_id": request.url_id,
        "application_name": request.application_name,
        "files_received": len(request.files),
        "text_files": len(text_files),
        "binary_files": len(binary_files),
        "messages_received": len(request.messages) if request.messages else 0,
        "stored": bool(request.chat_id or request.url_id),
        "saved_to_file": saved_file_path,
        "timestamp": datetime.now().isoformat(),
        "agent_state_updated": bool(artifact_id)
    }

# Refactor the chat endpoint

from .utils.message_converter import (
    convert_chat_messages_to_langchain,
    convert_log_entries_to_messages,
    combine_messages
)

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    logger.info("--- Entering chat_endpoint ---")
    
    try:
        # Update agent state using the unified method
        state_updates = {}
        
        # Set reasoning mode directly in agent state
        state_updates['use_planner'] = request.use_reasoning
        
        # Apply all updates at once
        if state_updates:
            app.state.agent.update_agent_state(**state_updates)
        
        # Convert messages using utility function
        langchain_messages = convert_chat_messages_to_langchain(
            messages=request.messages,
            include_images=True,
            image_only_on_last=True
        )
        
        logger.info(f"Processed {len(langchain_messages)} messages for chat")
        
        # Direct streaming from MCP agent
        return StreamingResponse(
            app.state.agent.stream_xml_content(input=langchain_messages),
            media_type="text/event-stream"
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# 1. Define a LogEntry model matching the frontend payload
class LogEntry(BaseModel):
    command: str
    stdout: str
    stderr: str
    exitCode: int
    success: bool
    first: Optional[bool] = False

# 2. Define a batch request model
class LogData(ChatRequest):
    files: Optional[Any] = None
    logs: List[LogEntry]

# 3. Update the /api/logs endpoint to accept the batch
@app.post("/api/logs")
async def receive_logs(log_data: LogData):
    try:
        logger.info(f"Received logs batch for thread {log_data.thread_id}, count: {len(log_data.logs)}")
        
        # Check if any log entry failed
        has_failures = any(not log.success for log in log_data.logs) if log_data.logs else False

        if not has_failures:
            logger.info("No failed log entries - returning status without agent processing")
            return {"success": True, "received": len(log_data.logs)}

        # Has failures - process with agent
        logger.info("Found failed log entries - processing with agent")
        
        # Convert different message types using utilities
        log_messages = convert_log_entries_to_messages(log_data.logs) if log_data.logs else []
        
        chat_messages = convert_chat_messages_to_langchain(
            messages=log_data.messages,
            include_images=True,
            image_only_on_last=False  # Allow images on any message in logs
        ) if log_data.messages else []
        
        # Combine all messages
        langchain_messages = combine_messages(log_messages, chat_messages)
        
        logger.info(f"Sending {len(langchain_messages)} messages to agent")
        
        return StreamingResponse(
            app.state.agent.stream_xml_content(input=langchain_messages),
            media_type="text/event-stream"
        )
        
    except Exception as e:
        logger.error(f"Error processing logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))