import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from ...models.artifact_models import FileItem, ArtifactMetadata, ProjectInfo, FilesRequest

logger = logging.getLogger(__name__)

SearchType = Literal["similarity", "mmr", "similarity_score_threshold"]

class VectorStoreManager:
    """Simplified vector store manager using retriever pattern"""
    
    def __init__(self, vector_store_dir: str):
        self.vector_store_dir = Path(vector_store_dir)
        self.vector_store_dir.mkdir(exist_ok=True)
        
        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings()
        
        # Text splitter for chunking
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )
        
        # Cache for loaded vector stores
        self._cache: Dict[str, FAISS] = {}
    
    def create_artifact_vectors(self, artifact_id: str, files: List[FileItem]) -> Optional[str]:
        """Create new vector store for an artifact"""
        try:
            # Create documents from files
            documents = self._files_to_documents(artifact_id, files)
            
            if not documents:
                logger.warning(f"No documents to vectorize for artifact: {artifact_id}")
                return None
            
            # Split documents into chunks
            chunked_docs = self.text_splitter.split_documents(documents)
            logger.info(f"Split {len(documents)} files into {len(chunked_docs)} chunks for {artifact_id}")
            
            # Create vector store
            vector_store = FAISS.from_documents(chunked_docs, self.embeddings)
            
            # Save vector store
            vector_path = self.vector_store_dir / artifact_id
            vector_store.save_local(str(vector_path))
            
            # Cache it
            self._cache[artifact_id] = vector_store
            
            # Save metadata
            self._save_vector_metadata(artifact_id, files, len(chunked_docs))
            
            logger.info(f"Created vector store for {artifact_id}: {len(chunked_docs)} vectors")
            return str(vector_path)
            
        except Exception as e:
            logger.error(f"Failed to create vectors for {artifact_id}: {e}")
            raise e
    
    def update_artifact_vectors(self, artifact_id: str, files: List[FileItem]) -> Optional[str]:
        """Update existing vector store or create new one"""
        try:
            vector_path = self.vector_store_dir / artifact_id
            
            if vector_path.exists():
                # Load existing metadata to compare
                metadata = self._load_vector_metadata(artifact_id)
                
                # Check if files have changed
                current_file_hashes = {f.path: hash(f.content) for f in files}
                stored_file_hashes = metadata.get('file_hashes', {})
                
                if current_file_hashes == stored_file_hashes:
                    logger.info(f"No changes detected for {artifact_id}, skipping vector update")
                    return str(vector_path)
            
            # Recreate vector store (simpler than incremental updates)
            return self.create_artifact_vectors(artifact_id, files)
            
        except Exception as e:
            logger.error(f"Failed to update vectors for {artifact_id}: {e}")
            raise e
    
    def get_vector_store(self, artifact_id: str) -> Optional[FAISS]:
        """Get vector store for an artifact"""
        try:
            if artifact_id in self._cache:
                return self._cache[artifact_id]
            
            vector_path = self.vector_store_dir / artifact_id
            if not vector_path.exists():
                logger.warning(f"Vector store not found for {artifact_id}")
                return None
            
            # Load vector store
            vector_store = FAISS.load_local(
                str(vector_path), 
                self.embeddings, 
                allow_dangerous_deserialization=True
            )
            self._cache[artifact_id] = vector_store
            
            logger.info(f"Loaded vector store for {artifact_id}")
            return vector_store
            
        except Exception as e:
            logger.error(f"Failed to load vector store for {artifact_id}: {e}")
            return None
    
    def get_retriever(
        self,
        artifact_id: str,
        search_type: SearchType = "similarity",
        search_kwargs: Optional[Dict[str, Any]] = None
    ) -> Optional[BaseRetriever]:
        """Get a retriever for an artifact with specified search configuration"""
        try:
            vector_store = self.get_vector_store(artifact_id)
            if not vector_store:
                return None
            
            # Default search kwargs
            default_kwargs = {"k": 5}
            if search_kwargs:
                default_kwargs.update(search_kwargs)
            
            # Create retriever with specified search type
            retriever = vector_store.as_retriever(
                search_type=search_type,
                search_kwargs=default_kwargs
            )
            
            logger.info(f"Created {search_type} retriever for {artifact_id}")
            return retriever
            
        except Exception as e:
            logger.error(f"Failed to create retriever for {artifact_id}: {e}")
            return None
    
    def search(
        self,
        artifact_id: str,
        query: str,
        search_type: SearchType = "similarity",
        search_kwargs: Optional[Dict[str, Any]] = None,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Universal search function using retriever pattern
        
        Args:
            artifact_id: ID of the artifact to search
            query: Search query
            search_type: Type of search ("similarity", "mmr", "similarity_score_threshold")
            search_kwargs: Additional search parameters (k, score_threshold, etc.)
            filter: Metadata filter (e.g., {"source": "news", "file_extension": "py"})
        
        Returns:
            List of relevant documents
        """
        try:
            # Get retriever
            retriever = self.get_retriever(artifact_id, search_type, search_kwargs)
            if not retriever:
                return []
            
            # Perform search with optional filter
            if filter:
                # For FAISS, we need to pass filter in search_kwargs
                current_kwargs = retriever.search_kwargs.copy()
                current_kwargs["filter"] = filter
                
                # Update retriever with filter
                vector_store = self.get_vector_store(artifact_id)
                retriever = vector_store.as_retriever(
                    search_type=search_type,
                    search_kwargs=current_kwargs
                )
            
            # Invoke retriever
            results = retriever.invoke(query)
            
            logger.info(f"Found {len(results)} results for '{query}' in {artifact_id}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to search {artifact_id}: {e}")
            return []
    
    def search_all_artifacts(
        self,
        query: str,
        search_type: SearchType = "similarity",
        search_kwargs: Optional[Dict[str, Any]] = None,
        filter: Optional[Dict[str, Any]] = None,
        max_results: int = 10
    ) -> List[Document]:
        """Search across all artifacts using retriever pattern"""
        try:
            all_results = []
            artifacts = self.list_artifacts()
            
            # Calculate k per artifact to get diverse results
            k_per_artifact = max(1, max_results // len(artifacts)) if artifacts else max_results
            
            # Override k in search_kwargs
            artifact_search_kwargs = (search_kwargs or {}).copy()
            artifact_search_kwargs["k"] = k_per_artifact
            
            for artifact_id in artifacts:
                results = self.search(
                    artifact_id=artifact_id,
                    query=query,
                    search_type=search_type,
                    search_kwargs=artifact_search_kwargs,
                    filter=filter
                )
                all_results.extend(results)
            
            # Return first max_results
            return all_results[:max_results]
            
        except Exception as e:
            logger.error(f"Failed to search all artifacts: {e}")
            return []
    
    def list_artifacts(self) -> List[str]:
        """List all artifacts with vector stores"""
        try:
            artifacts = []
            for artifact_dir in self.vector_store_dir.iterdir():
                if artifact_dir.is_dir() and (artifact_dir / "index.faiss").exists():
                    artifacts.append(artifact_dir.name)
            return artifacts
        except Exception as e:
            logger.error(f"Failed to list artifacts: {e}")
            return []
    
    def delete_artifact_vectors(self, artifact_id: str) -> bool:
        """Delete vector store for an artifact"""
        try:
            vector_path = self.vector_store_dir / artifact_id
            if vector_path.exists():
                import shutil
                shutil.rmtree(vector_path)
                
                # Remove from cache
                if artifact_id in self._cache:
                    del self._cache[artifact_id]
                
                logger.info(f"Deleted vector store for {artifact_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete vectors for {artifact_id}: {e}")
            return False
    
    def _files_to_documents(self, artifact_id: str, files: List[FileItem]) -> List[Document]:
        """Convert files to LangChain documents"""
        documents = []
        
        for file in files:
            # Skip binary files and very small files
            if file.is_binary or file.size < 10:
                continue
            
            # Skip certain file types
            if any(file.path.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg']):
                continue
            
            # Determine file extension for metadata
            file_extension = Path(file.path).suffix.lstrip('.')
            
            # Create document with enhanced metadata
            doc = Document(
                page_content=file.content,
                metadata={
                    "artifact_id": artifact_id,
                    "file_path": file.path,
                    "file_name": Path(file.path).name,
                    "file_extension": file_extension,
                    "file_size": file.size,
                    "file_type": file.type,
                    "is_binary": file.is_binary,
                    "source": "artifact_file"  # For filtering
                }
            )
            documents.append(doc)
        
        return documents
    
    def _save_vector_metadata(self, artifact_id: str, files: List[FileItem], vector_count: int):
        """Save metadata about the vector store"""
        try:
            metadata = {
                "artifact_id": artifact_id,
                "created_at": datetime.now().isoformat(),
                "file_count": len(files),
                "vector_count": vector_count,
                "file_hashes": {f.path: hash(f.content) for f in files},
                "file_paths": [f.path for f in files],
                "file_extensions": list(set(Path(f.path).suffix.lstrip('.') for f in files if Path(f.path).suffix))
            }
            
            metadata_path = self.vector_store_dir / artifact_id / "metadata.json"
            metadata_path.parent.mkdir(exist_ok=True)
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
                
        except Exception as e:
            logger.warning(f"Failed to save vector metadata for {artifact_id}: {e}")
    
    def _load_vector_metadata(self, artifact_id: str) -> Dict[str, Any]:
        """Load metadata about the vector store"""
        try:
            metadata_path = self.vector_store_dir / artifact_id / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.warning(f"Failed to load vector metadata for {artifact_id}: {e}")
            return {}