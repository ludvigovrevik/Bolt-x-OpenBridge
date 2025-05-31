import json
from pathlib import Path
from datetime import datetime
import logging
from ..models.artifact_models import FilesRequest, SavedArtifact, ArtifactMetadata, ProjectInfo, FileItem
from ..vector_store.manager.vector_manager import VectorStoreManager
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

def save_artifact_to_file(request: FilesRequest) -> str:
    """Save artifact by merging new files with existing ones and update vector store"""
    try:
        # Create storage directories
        storage_dir = Path.cwd() / "storage"
        files_dir = storage_dir / "files"
        vector_dir = storage_dir / "vector_store"
        
        storage_dir.mkdir(exist_ok=True)
        files_dir.mkdir(exist_ok=True)
        vector_dir.mkdir(exist_ok=True)
        
        # Generate filename
        filename = request.url_id or request.chat_id or request.artifact_id
        if not filename:
            filename = f"artifact_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        filename = "".join(c for c in filename if c.isalnum() or c in ('-', '_')).rstrip()
        file_path = files_dir / f"{filename}.json"
        
        # Load existing artifact if it exists
        existing_files: Dict[str, FileItem] = {}
        existing_metadata = None
        existing_messages = []
        is_update = False
        
        if file_path.exists():
            try:
                logger.info(f"Loading existing artifact from: {file_path}")
                existing_artifact = load_artifact_from_file(str(file_path))
                
                # Convert existing files to dict for easy lookup by path
                existing_files = {f.path: f for f in existing_artifact.files}
                existing_metadata = existing_artifact.metadata
                existing_messages = existing_artifact.messages or []
                is_update = True
                
                logger.info(f"Found {len(existing_files)} existing files")
                
            except Exception as e:
                logger.warning(f"Failed to load existing artifact, creating new one: {e}")
        
        # Extract project info from package.json in new files
        project_info = existing_metadata.project_info if existing_metadata else None
        package_json_file = next((f for f in request.files if 'package.json' in f.path), None)
        if package_json_file:
            try:
                package_data = json.loads(package_json_file.content)
                project_info = ProjectInfo(
                    name=package_data.get('name'),
                    version=package_data.get('version'),
                    description=package_data.get('description'),
                    dependencies=package_data.get('dependencies', {}),
                    scripts=package_data.get('scripts', {}),
                    dependencies_count=len(package_data.get('dependencies', {}))
                )
            except Exception as e:
                logger.warning(f"Failed to parse package.json: {e}")
        
        # Merge files: new files override existing ones, keep files not in new request
        merged_files = existing_files.copy()  # Start with existing files
        new_files_count = 0
        updated_files_count = 0
        files_changed = False  # Track if any files actually changed
        
        for new_file in request.files:
            if new_file.path in merged_files:
                # File exists, check if content changed
                if merged_files[new_file.path].content != new_file.content:
                    logger.info(f"Updating existing file: {new_file.path}")
                    merged_files[new_file.path] = new_file
                    updated_files_count += 1
                    files_changed = True
                else:
                    logger.debug(f"File unchanged: {new_file.path}")
            else:
                # New file, add it
                logger.info(f"Adding new file: {new_file.path}")
                merged_files[new_file.path] = new_file
                new_files_count += 1
                files_changed = True
        
        # Convert back to list
        final_files = list(merged_files.values())
        
        logger.info(f"File merge summary: {new_files_count} new, {updated_files_count} updated, {len(final_files)} total")
        
        # Merge messages - append new messages to existing ones
        merged_messages = existing_messages.copy()
        if request.messages:
            for new_msg in request.messages:
                # Check if message already exists (simple content comparison)
                if not any(existing_msg.content == new_msg.content for existing_msg in merged_messages):
                    merged_messages.append(new_msg)
                    logger.debug(f"Added new message from {new_msg.role}")
        
        # Create metadata - use new metadata but preserve original creation time
        metadata = ArtifactMetadata(
            artifact_id=request.artifact_id,
            message_id=request.message_id,
            chat_id=request.chat_id,
            url_id=request.url_id,
            application_name=request.application_name or (existing_metadata.application_name if existing_metadata else None),
            thread_id=request.thread_id,
            created_at=existing_metadata.created_at if existing_metadata else datetime.now().isoformat(),
            file_count=len(final_files),
            total_size=sum(f.size for f in final_files),
            project_info=project_info
        )
        
        # Add updated_at field if this is an update
        if existing_metadata:
            # Add custom field for tracking updates
            metadata_dict = metadata.dict()
            metadata_dict['updated_at'] = datetime.now().isoformat()
            metadata_dict['update_count'] = getattr(existing_metadata, 'update_count', 0) + 1
        else:
            metadata_dict = metadata.dict()
            metadata_dict['update_count'] = 0
        
        # Create the complete artifact
        artifact_dict = {
            "metadata": metadata_dict,
            "files": [f.dict() for f in final_files],
            "messages": [msg.dict() for msg in merged_messages]
        }
        
        # Save to JSON
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(artifact_dict, f, indent=2, ensure_ascii=False)
        
        # Update vector store ONLY if files actually changed
        try:
            vector_manager = VectorStoreManager(vector_dir)
            
            if files_changed:
                if is_update:
                    logger.info(f"Files changed, updating vector store for: {filename}")
                    vector_manager.update_artifact_vectors(filename, final_files)
                else:
                    logger.info(f"Creating new vector store for: {filename}")
                    vector_manager.create_artifact_vectors(filename, final_files)
                logger.info(f"Vector store updated for artifact: {filename}")
            else:
                logger.info(f"No file changes detected, skipping vector store update for: {filename}")
                
        except Exception as e:
            logger.error(f"Failed to update vector store: {e}")
            # Don't fail the entire save if vector store update fails
        
        # Verify file was written
        file_size = file_path.stat().st_size
        action = "updated" if existing_metadata else "created"
        logger.info(f"Artifact {action}: {file_path} ({file_size} bytes)")
        
        return str(file_path)
        
    except Exception as e:
        logger.error(f"Failed to save artifact: {e}")
        raise e
    

# Helper function to construct artifact path (for consistency)
def get_artifact_path(artifact_id: str) -> str:
    """Get the full file path for an artifact given its ID"""
    storage_dir = Path.cwd() / "storage" / "files"
    file_path = storage_dir / f"{artifact_id}.json"
    return str(file_path)  # Just return the path string

def artifact_exists(artifact_id: str) -> bool:
    """Check if an artifact exists"""
    file_path = Path(get_artifact_path(artifact_id))  # Convert back to Path for exists check
    return file_path.exists()

def load_artifact_from_file(file_path: str) -> SavedArtifact:
    """Load and validate artifact using Pydantic models"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Use Pydantic model for validation
        artifact = SavedArtifact(**data)
        return artifact
        
    except Exception as e:
        logger.error(f"Failed to load artifact from {file_path}: {e}")
        raise e

def get_artifact_files(artifact_id: str) -> List[str]:
    """Get list of file paths from an artifact using artifact_id"""
    try:
        if not artifact_exists(artifact_id):
            logger.warning(f"Artifact {artifact_id} not found")
            return []
            
        file_path = get_artifact_path(artifact_id)
        artifact = load_artifact_from_file(file_path)
        return [file_item.path for file_item in artifact.files]
        
    except Exception as e:
        logger.error(f"Failed to get files from artifact {artifact_id}: {e}")
        return []

def get_artifact_summary(artifact_id: str) -> Dict:
    """Get summary info about an artifact using artifact_id"""
    try:
        if not artifact_exists(artifact_id):
            logger.warning(f"Artifact {artifact_id} not found")
            return {}
            
        file_path = get_artifact_path(artifact_id)
        artifact = load_artifact_from_file(file_path)
        
        return {
            "file_count": len(artifact.files),
            "total_size": sum(f.size for f in artifact.files),
            "created_at": artifact.metadata.created_at,
            "updated_at": getattr(artifact.metadata, 'updated_at', None),
            "update_count": getattr(artifact.metadata, 'update_count', 0),
            "application_name": artifact.metadata.application_name,
            "project_name": artifact.metadata.project_info.name if artifact.metadata.project_info else None,
            "file_paths": [f.path for f in artifact.files]
        }
    except Exception as e:
        logger.error(f"Failed to get artifact summary for {artifact_id}: {e}")
        return {}