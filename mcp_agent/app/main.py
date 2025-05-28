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


import logging # Add logging import
import uuid

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


from .mcp_agent import MCPAgent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define a more specific type for the message data if needed, or use Any
class MessageData(BaseModel):
    imageData: Optional[str] = None

class ChatMessage(BaseModel):
    role: str
    content: str
    data: Optional[MessageData] = None

class ChatRequest(BaseModel):
    messages: List[ChatMessage] # Use the new ChatMessage model
    thread_id: str = "" 
    stream: bool = True
    use_reasoning: bool = False

# Add file-related models after your existing models
class FileData(BaseModel):
    path: str
    content: str
    type: str = "file"  # "file" or "directory"

class FileStore(BaseModel):
    files: Dict[str, FileData] = {}
    project_name: str = ""
    created_at: str = ""
    updated_at: str = ""

class FilesRequest(BaseModel):
    files: Dict[str, FileData]
    project_name: Optional[str] = None

from .tools.artifact_spec import artifact_spec
from .graph import ArtifactSpec

@app.on_event("startup")
async def startup_event():
    app.state.agent = MCPAgent()
    await app.state.agent.initialize() # Initialize the agent
    # Additional setup if needed
    #app.state.agent.tools.append()
    logger.info(f"Agent initialized with tools: {app.state.agent.tools}")
    print("Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state.agent, 'cleanup'):
        await app.state.agent.cleanup()
    # Additional cleanup if needed
    print("Application shutdown complete")


# Global file store (in production, use Redis or database)
file_stores: Dict[str, FileStore] = {}

# Add this function after your imports but before the endpoints

async def stream_agent_response(messages: List[BaseMessage], use_reasoning: bool = True):
    """
    Helper function to stream responses from the agent.
    
    Args:
        messages: List of LangChain messages to send to the agent
        use_reasoning: Whether to enable reasoning in the agent
        
    Returns:
        StreamingResponse object for the FastAPI endpoint
    """
    try:
        # Set agent reasoning mode if needed
        await app.state.agent.set_agent_type(reasoning=use_reasoning)
        logger.info(f"Agent set to reasoning: {use_reasoning}")
        
        # Log the messages being sent
        logger.info(f"Sending {len(messages)} messages to agent")
        
        # Create streaming function
        async def event_stream():
            """Stream formatted content directly from the agent's artifact stream."""
            async for content in app.state.agent.stream_xml_content(
                input=messages,
            ):
                # Direct yield without additional processing
                yield content
        
        logger.info("Streaming agent response")
        return StreamingResponse(event_stream(), media_type="text/event-stream")
    
    except Exception as e:
        logger.error(f"Error in agent streaming: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Refactor the chat endpoint

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    logger.info("--- Entering chat_endpoint ---")
    
    try:
        # Process the incoming messages
        langchain_messages: List[BaseMessage] = []
        num_messages = len(request.messages)
        
        # Optional: Add file context if available
        files_context = ""
        if hasattr(request, 'thread_id') and request.thread_id in file_stores:
            store = file_stores[request.thread_id]
            if store.files:
                files_context = f"\n\n**Current Project Context:**\n"
                files_context += f"Project: {store.project_name}\n"
                files_context += f"Files: {len(store.files)} files available\n"
                # Add recent files
                recent_files = list(store.files.items())[:3]  # Show first 3 files
                for path, file_data in recent_files:
                    files_context += f"- {path} ({file_data.type})\n"
        
        for i, msg in enumerate(request.messages):
            role = msg.role
            content = msg.content
            is_last_message = (i == num_messages - 1)

            if role == 'user':
                # Add file context to the last user message if available
                if is_last_message and files_context:
                    content = f"{content}{files_context}"
                
                # Handle user messages, including multimodal
                image_data = msg.data.imageData if msg.data and msg.data.imageData and is_last_message else None

                if image_data:
                    message_content = [
                        {"type": "text", "text": content},
                        {"type": "image_url", "image_url": {"url": image_data}}
                    ]
                    langchain_messages.append(HumanMessage(content=message_content))
                    logger.info(f"Processed multimodal user message: {content[:50]}... + Image")
                else:
                    langchain_messages.append(HumanMessage(content=content))
                    
            elif role == 'assistant':
                langchain_messages.append(AIMessage(content=content))
        
        logger.info(f"Processed {len(langchain_messages)} messages for chat")
        
        # Use the shared streaming function
        return await stream_agent_response(
            messages=langchain_messages,
            use_reasoning=request.use_reasoning
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))




# Update the LogData class - keep it simple
class LogData(ChatRequest):
    formatted_error: Optional[str] = None
    success: Optional[bool] = True

from pydantic import BaseModel
from typing import List, Optional

# 1. Define a LogEntry model matching the frontend payload
class LogEntry(BaseModel):
    command: str
    stdout: str
    stderr: str
    exitCode: int
    success: bool
    first: Optional[bool] = False

# 2. Define a batch request model
class LogData(BaseModel):
    logs: List[LogEntry]
    thread_id: Optional[str] = None
    stream: Optional[bool] = True
    use_reasoning: Optional[bool] = False
    messages: Optional[List[ChatMessage]] = None
    files: Optional[Any] = None

# 3. Update the /api/logs endpoint to accept the batch
@app.post("/api/logs")
async def receive_logs(batch: LogData):
    logger.info(f"Received logs batch for thread {batch.thread_id}, count: {len(batch.logs)}")
    if batch.logs:
        for log in batch.logs:
            logger.info(
                f"[{'FIRST' if log.first else ''}] Command: {log.command} | "
                f"Success: {log.success} | Exit: {log.exitCode} | "
                f"Stdout: {log.stdout} | Stderr: {log.stderr}"
            )

    if batch.messages:
        logger.info(f"Received {len(batch.messages)} messages with logs")
    
    if batch.files:
        logger.info(f"Received file modifications with logs")
    

        # Here you can process/store logs as needed
    return {"success": True, "received": len(batch.logs)}


async def maybe(log_data: LogData):
    logger.info(f"Received logs request")
    logger.info(f"Log data messages: {log_data.messages}")
    logger.info(f"Log data formatted error: {log_data.formatted_error}")
    logger.info(f"Logs recieved with {log_data.success}")
    try:
        # Check if we have messages - this is the new format coming from frontend
        if log_data.messages and len(log_data.messages) > 0:
            
            # Convert the messages to LangChain format
            langchain_messages = []
            
            for msg in log_data.messages:
                if msg.role == 'user':
                    # Handle multimodal content if present
                    if msg.data and msg.data.imageData:
                        message_content = [
                            {"type": "text", "text": msg.content},
                            {"type": "image_url", "image_url": {"url": msg.data.imageData}}
                        ]
                        langchain_messages.append(HumanMessage(content=message_content))
                    else:
                        langchain_messages.append(HumanMessage(content=msg.content))
                elif msg.role == 'assistant':
                    langchain_messages.append(AIMessage(content=msg.content))
            
            # Use the shared streaming function
            logger.info(f"Sending {len(langchain_messages)} messages to agent")
            # return await stream_agent_response(
            #     messages=langchain_messages,
            #     use_reasoning=log_data.use_reasoning
            # )
            return True
    except Exception as e:
        logger.error(f"Error processing logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



class FileItem(BaseModel):
    path: str
    content: str
    is_binary: bool = False
    size: int = 0

class FilesRequest(BaseModel):
    artifact_id: str
    message_id: Optional[str] = None
    chat_id: Optional[str] = None
    url_id: Optional[str] = None
    application_name: Optional[str] = None
    thread_id: Optional[str] = None
    files: List[FileItem] = []
    messages: Optional[List[ChatMessage]] = None
    file_count: Optional[int] = None

import json
import os
from pathlib import Path

def save_artifact_to_file(request: FilesRequest) -> str:
    """Save artifact files to JSON file in cwd/files/url_id.json format"""
    try:
        # Create files directory if it doesn't exist
        files_dir = Path.cwd() / "files"
        files_dir.mkdir(exist_ok=True)
        
        # Use url_id or chat_id as filename, fallback to artifact_id
        filename = request.url_id or request.chat_id or request.artifact_id
        if not filename:
            filename = f"artifact_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Ensure valid filename
        filename = "".join(c for c in filename if c.isalnum() or c in ('-', '_')).rstrip()
        file_path = files_dir / f"{filename}.json"
        
        # Extract project info from package.json if available
        project_info = {}
        package_json_file = next((f for f in request.files if 'package.json' in f.path), None)
        if package_json_file:
            try:
                package_data = json.loads(package_json_file.content)
                project_info = {
                    'name': package_data.get('name'),
                    'version': package_data.get('version'),
                    'description': package_data.get('description'),
                    'dependencies': package_data.get('dependencies', {}),
                    'scripts': package_data.get('scripts', {}),
                }
            except Exception as e:
                logger.warning(f"Failed to parse package.json: {e}")
        
        # Prepare artifact data
        artifact_data = {
            "metadata": {
                "artifact_id": request.artifact_id,
                "message_id": request.message_id,
                "chat_id": request.chat_id,
                "url_id": request.url_id,
                "application_name": request.application_name,
                "thread_id": request.thread_id,
                "created_at": datetime.now().isoformat(),
                "file_count": len(request.files),
                "project_info": project_info
            },
            "files": [
                {
                    "path": file.path,
                    "content": file.content,
                    "is_binary": file.is_binary,
                    "size": file.size,
                    "type": "binary" if file.is_binary else "text"
                }
                for file in request.files
            ],
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "data": msg.data.dict() if msg.data else None
                }
                for msg in (request.messages or [])
            ] if request.messages else []
        }
        
        # Write to JSON file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(artifact_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Artifact saved to: {file_path}")
        return str(file_path)
        
    except Exception as e:
        logger.error(f"Failed to save artifact to file: {e}")
        raise e

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
        # Continue processing even if file save fails
        saved_file_path = None
    
    # Extract project info from package.json if available
    project_info = {}
    package_json_file = next((f for f in request.files if 'package.json' in f.path), None)
    if package_json_file:
        try:
            package_data = json.loads(package_json_file.content)
            project_info = {
                'name': package_data.get('name'),
                'version': package_data.get('version'),
                'description': package_data.get('description'),
                'dependencies_count': len(package_data.get('dependencies', {}))
            }
            logger.info(f"Project info extracted: {project_info}")
        except Exception as e:
            logger.warning(f"Failed to parse package.json: {e}")
    
    # Store files in memory (keep existing functionality)
    if request.chat_id or request.url_id:
        store_key = request.chat_id or request.url_id
        file_stores[store_key] = FileStore(
            files={f.path: FileData(
                path=f.path,
                content=f.content,
                type="file" if not f.is_binary else "binary"
            ) for f in request.files},
            project_name=project_info.get('name', request.application_name or 'Unknown'),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        logger.info(f"Stored files in memory for key: {store_key}")
    
    # You can also trigger AI analysis here if needed
    if request.messages and len(request.files) > 0:
        logger.info("Files received with chat context - could trigger AI analysis")
        # TODO: Implement AI analysis of files + chat context
    
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
        "project_info": project_info,
        "stored": bool(request.chat_id or request.url_id),
        "saved_to_file": saved_file_path,
        "timestamp": datetime.now().isoformat()
    }