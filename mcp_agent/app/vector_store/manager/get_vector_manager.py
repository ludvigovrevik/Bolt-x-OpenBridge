from datetime import datetime
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from ..manager.vector_manager import VectorStoreManager

logger = logging.getLogger(__name__)

# Global vector manager instance
_vector_manager: Optional[VectorStoreManager] = None

def get_vector_manager() -> VectorStoreManager:
    """Get or create the global vector store manager"""
    global _vector_manager
    if _vector_manager is None:
        storage_dir = Path.cwd() / "storage" / "vector_store"
        _vector_manager = VectorStoreManager(str(storage_dir))
    return _vector_manager
