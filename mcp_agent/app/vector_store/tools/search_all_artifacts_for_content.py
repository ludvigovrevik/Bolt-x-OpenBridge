from datetime import datetime
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

from ..manager.get_vector_manager import get_vector_manager

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