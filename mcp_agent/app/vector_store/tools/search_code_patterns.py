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