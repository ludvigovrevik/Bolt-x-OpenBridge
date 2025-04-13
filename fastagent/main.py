from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import json
import os
import asyncio
from dotenv import load_dotenv
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from typing import Any, Dict, List, Union, Optional, Callable
from prompt import get_prompt

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    messages: list[dict]
    stream: bool = True
    mock_response: Optional[str] = None

llm = ChatOpenAI(
    temperature=0,
    model="gpt-4",
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    streaming=True
)

WEB_CONTAINER_WORK_DIR = "/home/project"

MAX_RESPONSE_SEGMENTS = 5
SYSTEM_PROMPT = get_prompt(WEB_CONTAINER_WORK_DIR)
CONTINUE_PROMPT = "Continue your prior response. IMPORTANT: Immediately begin from where you left off without any interruptions. Do not repeat any content, including artifact and action tags."

async def generate(messages: list[dict]):
    """
    Generator function to yield responses from the LLM.
    """
    content_buffer = ""
    in_artifact = False
    async for chunk in llm.astream(messages):
        chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)

        if chunk_content:
            content_buffer += chunk_content

            # Check for artifact boundaries
            if "<boltArtifact" in chunk_content:
                in_artifact = True
            if "</boltArtifact>" in chunk_content:
                in_artifact = False

            yield f"data: {json.dumps({'text': chunk_content, 'inArtifact': in_artifact})}\n\n"

    yield "data: [DONE]\n\n"

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    if request.mock_response:
        async def mock_generate():
            for char in request.mock_response:
                await asyncio.sleep(0.01)
                yield f"data: {json.dumps({'text': char, 'inArtifact': '<boltArtifact' in request.mock_response and '</boltArtifact>' not in char})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(mock_generate(), media_type="text/event-stream")

    try:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT)
        ]

        for message in request.messages:
            if message["role"] == "user":
                messages.append(HumanMessage(content=message["content"]))
            elif message["role"] == "assistant":
                messages.append(AIMessage(content=message["content"]))

        return StreamingResponse(generate(messages), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=json.dumps({
            "error": str(e),
            "statusText": "Internal Server Error"
        }))