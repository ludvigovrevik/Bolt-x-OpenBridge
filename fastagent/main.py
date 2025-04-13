from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import json
import os
import asyncio
from dotenv import load_dotenv
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from typing import Any, Dict, List, Union, Optional
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


llm = ChatOpenAI(
    temperature=0,
    model="gpt-4",  # Changed from "gpt-4o-mini" as this isn't a valid model name
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    streaming=True
)

WEB_CONTAINER_WORK_DIR = "/home/project" 

MAX_RESPONSE_SEGMENTS = 5
# Add this near the top of your FastAPI file
SYSTEM_PROMPT = get_prompt(WEB_CONTAINER_WORK_DIR)

CONTINUE_PROMPT = "Continue your prior response. IMPORTANT: Immediately begin from where you left off without any interruptions. Do not repeat any content, including artifact and action tags."

MOCK_RESPONSE = """
<boltArtifact id="my-script" title="Running a Node.js script">
  <boltAction type="file" filePath="index.js">
    console.log("Hello from Node.js!");
  </boltAction>
  <boltAction type="shell">
    node index.js
  </boltAction>
</boltArtifact>
"""

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    if MOCK_RESPONSE:
        async def mock_generate():
            for char in MOCK_RESPONSE:
                await asyncio.sleep(0.01)  # Simulate streaming
                print(char)
                yield f"data: {json.dumps({'text': char, 'inArtifact': '<boltArtifact' in MOCK_RESPONSE and '</boltArtifact>' not in char})}\n\n"
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

        async def generate():
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

                    # Send valid JSON-serializable data
                    data = f"data: {json.dumps({'text': content_buffer, 'inArtifact': in_artifact})}\n\n"
                    print(data)
                    yield data

            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=json.dumps({
            "error": str(e),
            "statusText": "Internal Server Error"
        }))
