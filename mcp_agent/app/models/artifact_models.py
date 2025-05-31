from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

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


class ProjectInfo(BaseModel):
    name: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    dependencies: Optional[Dict[str, str]] = None
    scripts: Optional[Dict[str, str]] = None
    dependencies_count: Optional[int] = None

class ArtifactMetadata(BaseModel):
    artifact_id: str
    message_id: Optional[str] = None
    chat_id: Optional[str] = None
    url_id: Optional[str] = None
    application_name: Optional[str] = None
    thread_id: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None  # Add this
    update_count: Optional[int] = 0   # Add this
    file_count: int
    total_size: Optional[int] = None
    project_info: Optional[ProjectInfo] = None

class FileItem(BaseModel):
    path: str
    content: str
    is_binary: bool = False
    size: int = 0
    type: str = "text"  # "text" or "binary"


class SavedArtifact(BaseModel):
    """Complete saved artifact structure matching the JSON file format"""
    metadata: ArtifactMetadata
    files: List[FileItem]
    messages: Optional[List[ChatMessage]] = None

class FilesRequest(BaseModel):
    """Request model for incoming file data"""
    artifact_id: str
    message_id: Optional[str] = None
    chat_id: Optional[str] = None
    url_id: Optional[str] = None
    application_name: Optional[str] = None
    thread_id: Optional[str] = None
    files: List[FileItem] = []
    messages: Optional[List[ChatMessage]] = None
    file_count: Optional[int] = None

class ArtifactSummary(BaseModel):
    """Summary information about an artifact for listing purposes"""
    filename: str
    url_id: Optional[str] = None
    artifact_id: Optional[str] = None
    application_name: Optional[str] = None
    created_at: Optional[str] = None
    file_count: int = 0
    total_size: int = 0
    project_name: Optional[str] = None
    file_size: int = 0
    files: Optional[List[str]] = None  # File paths only

class ArtifactFilesResponse(BaseModel):
    """Response model for artifact file listings"""
    url_id: str
    application_name: Optional[str] = None
    artifact_id: Optional[str] = None
    created_at: Optional[str] = None
    file_count: int
    files: List[str]  # File paths

class FileContentResponse(BaseModel):
    """Response model for individual file content"""
    path: str
    content: str
    is_binary: bool
    size: int
    type: str