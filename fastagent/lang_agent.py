from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_openai import ChatOpenAI
import json
import os

from dotenv import load_dotenv
from pydantic import BaseModel
load_dotenv()
from fastapi.responses import StreamingResponse

llm = ChatOpenAI(
    temperature=0,
    model="gpt-4o-mini",
    openai_api_key=os.getenv("OPENAI_API_KEY"),
)

    
async def generate():
    stream_content = llm.astream(
        input="halla")
    content = ""
    async for chunk in stream_content:
        content += chunk.content
        print(content)

if  __name__ == "__main__":
    import asyncio
    asyncio.run(generate())
