from datetime import datetime
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from ..manager.vector_manager import VectorStoreManager

logger = logging.getLogger(__name__)

from ..manager.get_vector_manager import get_vector_manager

@tool
def retrieve_file_contents(
    query: str,
    artifact_id: str,
    search_type: str = "similarity",
    search_kwargs: Optional[Dict[str, Any]] = None,
    filter: Optional[Dict[str, Any]] = None,
    max_content_length: int = 10000
) -> List[Dict[str, Any]]:
    """
    Retrieve file names and contents from a specific artifact based on a query.
    This tool returns the actual file content for the LLM to analyze.
    
    Args:
        query (str): The search query to find relevant files.
        artifact_id (str): The ID of the artifact to search in.
        search_type (str): Type of search ("similarity", "mmr", "similarity_score_threshold").
        search_kwargs (Optional[Dict[str, Any]]): Additional search parameters like {"k": 5}.
        filter (Optional[Dict[str, Any]]): Filter criteria like {"source": "python"}.
        max_content_length (int): Maximum length of content to return per file (default: 10000).
        
    Returns:
        List[Dict[str, Any]]: A list of files with names and contents matching the query.
    """
    try:
        vector_manager = get_vector_manager()
        results = vector_manager.search(
            artifact_id=artifact_id,
            query=query,
            search_type=search_type,
            search_kwargs=search_kwargs,
            filter=filter
        )
        
        if not results:
            logger.info(f"No files found for query '{query}' in artifact '{artifact_id}'")
            return []
        
        # Format results with content for LLM analysis
        formatted_results = []
        for doc in results:
            # Truncate content if too long
            content = doc.page_content
            if len(content) > max_content_length:
                content = content[:max_content_length] + "\n\n... [Content truncated]"
            
            result = {
                "file_name": doc.metadata.get("file_name", "Unknown"),
                "file_path": doc.metadata.get("file_path", "Unknown"),
                "file_extension": doc.metadata.get("file_extension", ""),
                "source": doc.metadata.get("source", ""),
                "content": content,
                "file_size": doc.metadata.get("file_size", 0),
                "artifact_id": doc.metadata.get("artifact_id")
            }
            formatted_results.append(result)
        
        logger.info(f"Retrieved {len(formatted_results)} files with content for query '{query}' in artifact '{artifact_id}'")
        return formatted_results
        
    except Exception as e:
        logger.error(f"Error retrieving file contents for query '{query}' in artifact '{artifact_id}': {e}")
        return []

@tool
def get_specific_file_content(
    artifact_id: str,
    file_path: str
) -> Dict[str, Any]:
    """
    Get the complete content of a specific file by its path.
    
    Args:
        artifact_id (str): The ID of the artifact containing the file.
        file_path (str): The exact path of the file to retrieve.
        
    Returns:
        Dict[str, Any]: File information with complete content, or empty dict if not found.
    """
    try:
        vector_manager = get_vector_manager()
        
        # Search for the exact file path
        results = vector_manager.search(
            artifact_id=artifact_id,
            query=file_path,
            search_type="similarity",
            search_kwargs={"k": 10},  # Get more results to find exact match
            filter=None
        )
        
        # Find exact file path match
        for doc in results:
            if doc.metadata.get("file_path") == file_path:
                return {
                    "file_name": doc.metadata.get("file_name"),
                    "file_path": doc.metadata.get("file_path"),
                    "file_extension": doc.metadata.get("file_extension"),
                    "source": doc.metadata.get("source"),
                    "content": doc.page_content,
                    "file_size": doc.metadata.get("file_size"),
                    "artifact_id": doc.metadata.get("artifact_id"),
                    "found": True
                }
        
        logger.warning(f"File not found: {file_path} in artifact {artifact_id}")
        return {"found": False, "error": f"File {file_path} not found in artifact {artifact_id}"}
        
    except Exception as e:
        logger.error(f"Error retrieving specific file {file_path} from artifact {artifact_id}: {e}")
        return {"found": False, "error": str(e)}

@tool
def search_code_patterns(
    pattern: str,
    artifact_id: str,
    language: Optional[str] = None,
    k: int = 5,
    include_context: bool = True
) -> List[Dict[str, Any]]:
    """
    Search for specific code patterns, functions, or classes in an artifact.
    Returns relevant code sections with context for LLM analysis.
    
    Args:
        pattern (str): Code pattern to search for (function names, class names, imports, etc.).
        artifact_id (str): The ID of the artifact to search in.
        language (str): Programming language to filter by ("python", "javascript", "react", etc.).
        k (int): Number of results to return.
        include_context (bool): Whether to include surrounding code context.
        
    Returns:
        List[Dict[str, Any]]: Code sections containing the pattern.
    """
    try:
        vector_manager = get_vector_manager()
        
        # Build filter for language
        filter_dict = {}
        if language:
            filter_dict["source"] = language
        
        results = vector_manager.search(
            artifact_id=artifact_id,
            query=pattern,
            search_type="similarity",
            search_kwargs={"k": k},
            filter=filter_dict if filter_dict else None
        )
        
        if not results:
            return []
        
        formatted_results = []
        for doc in results:
            content = doc.page_content
            
            # If include_context is False, try to extract just the relevant section
            if not include_context:
                lines = content.split('\n')
                relevant_lines = []
                for i, line in enumerate(lines):
                    if pattern.lower() in line.lower():
                        # Include some context around the match
                        start = max(0, i - 2)
                        end = min(len(lines), i + 3)
                        relevant_lines.extend(lines[start:end])
                        break
                content = '\n'.join(relevant_lines) if relevant_lines else content
            
            result = {
                "file_name": doc.metadata.get("file_name"),
                "file_path": doc.metadata.get("file_path"),
                "language": doc.metadata.get("source"),
                "pattern_found": pattern,
                "code_content": content,
                "file_size": doc.metadata.get("file_size")
            }
            formatted_results.append(result)
        
        return formatted_results
        
    except Exception as e:
        logger.error(f"Error searching for pattern '{pattern}' in artifact {artifact_id}: {e}")
        return []

@tool
def search_all_artifacts_for_content(
    query: str,
    search_type: str = "mmr",
    max_results: int = 5,
    filter: Optional[Dict[str, Any]] = None,
    max_content_length: int = 8000
) -> List[Dict[str, Any]]:
    """
    Search across all artifacts and return file contents for LLM analysis.
    
    Args:
        query (str): The search query.
        search_type (str): Type of search ("similarity", "mmr", "similarity_score_threshold").
        max_results (int): Maximum number of results to return.
        filter (Optional[Dict[str, Any]]): Filter criteria.
        max_content_length (int): Maximum content length per file.
        
    Returns:
        List[Dict[str, Any]]: Files with content from all artifacts.
    """
    try:
        vector_manager = get_vector_manager()
        results = vector_manager.search_all_artifacts(
            query=query,
            search_type=search_type,
            filter=filter,
            max_results=max_results
        )
        
        if not results:
            return []
        
        formatted_results = []
        for doc in results:
            content = doc.page_content
            if len(content) > max_content_length:
                content = content[:max_content_length] + "\n\n... [Content truncated]"
            
            result = {
                "artifact_id": doc.metadata.get("artifact_id"),
                "file_name": doc.metadata.get("file_name"),
                "file_path": doc.metadata.get("file_path"),
                "source": doc.metadata.get("source"),
                "content": content,
                "file_size": doc.metadata.get("file_size")
            }
            formatted_results.append(result)
        
        return formatted_results
        
    except Exception as e:
        logger.error(f"Error searching all artifacts for '{query}': {e}")
        return []