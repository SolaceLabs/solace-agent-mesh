"""
Embedding service for skill semantic search.

This service generates embeddings for skills using various
embedding providers (OpenAI, local models, etc.) and provides
vector similarity search capabilities.
"""

import logging
import numpy as np
from typing import Optional, List, Dict, Any, Tuple
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""
    
    @abstractmethod
    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        pass
    
    @abstractmethod
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name."""
        pass
    
    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        pass


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider using text-embedding-3-small."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small",
        base_url: Optional[str] = None,
    ):
        """
        Initialize OpenAI embedding provider.
        
        Args:
            api_key: OpenAI API key (uses OPENAI_API_KEY env var if not provided)
            model: Model name to use
            base_url: Optional base URL for API (for proxies)
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package required for OpenAI embeddings")
        
        self._model = model
        self._dimension = 1536 if "small" in model else 3072
        
        client_kwargs = {}
        if api_key:
            client_kwargs["api_key"] = api_key
        if base_url:
            client_kwargs["base_url"] = base_url
        
        self.client = OpenAI(**client_kwargs)
    
    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        response = self.client.embeddings.create(
            model=self._model,
            input=text,
        )
        return response.data[0].embedding
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        response = self.client.embeddings.create(
            model=self._model,
            input=texts,
        )
        return [item.embedding for item in response.data]
    
    @property
    def model_name(self) -> str:
        return self._model
    
    @property
    def dimension(self) -> int:
        return self._dimension


class LiteLLMEmbeddingProvider(EmbeddingProvider):
    """LiteLLM embedding provider for various models."""
    
    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize LiteLLM embedding provider.
        
        Args:
            model: Model name to use
            api_base: Optional API base URL
            api_key: Optional API key
        """
        try:
            import litellm
            self.litellm = litellm
        except ImportError:
            raise ImportError("litellm package required for LiteLLM embeddings")
        
        self._model = model
        self._api_base = api_base
        self._api_key = api_key
        
        # Estimate dimension based on model
        if "small" in model:
            self._dimension = 1536
        elif "large" in model:
            self._dimension = 3072
        else:
            self._dimension = 1536  # Default
    
    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        kwargs = {"model": self._model, "input": [text]}
        if self._api_base:
            kwargs["api_base"] = self._api_base
        if self._api_key:
            kwargs["api_key"] = self._api_key
        
        response = self.litellm.embedding(**kwargs)
        return response.data[0]["embedding"]
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        kwargs = {"model": self._model, "input": texts}
        if self._api_base:
            kwargs["api_base"] = self._api_base
        if self._api_key:
            kwargs["api_key"] = self._api_key
        
        response = self.litellm.embedding(**kwargs)
        return [item["embedding"] for item in response.data]
    
    @property
    def model_name(self) -> str:
        return self._model
    
    @property
    def dimension(self) -> int:
        return self._dimension


class EmbeddingService:
    """
    Service for generating and searching skill embeddings.
    
    Provides:
    - Embedding generation for skills
    - Vector similarity search
    - Caching of embeddings
    """
    
    def __init__(
        self,
        provider: Optional[EmbeddingProvider] = None,
        provider_type: str = "openai",
        **provider_kwargs,
    ):
        """
        Initialize the embedding service.
        
        Args:
            provider: Optional pre-configured provider
            provider_type: Type of provider to create if not provided
            **provider_kwargs: Arguments to pass to provider constructor
        """
        if provider:
            self.provider = provider
        else:
            self.provider = self._create_provider(provider_type, **provider_kwargs)
        
        # In-memory cache for embeddings
        self._cache: Dict[str, List[float]] = {}
    
    def _create_provider(
        self, 
        provider_type: str, 
        **kwargs
    ) -> EmbeddingProvider:
        """Create an embedding provider by type."""
        if provider_type == "openai":
            return OpenAIEmbeddingProvider(**kwargs)
        elif provider_type == "litellm":
            return LiteLLMEmbeddingProvider(**kwargs)
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")
    
    def get_skill_embedding(
        self,
        skill_name: str,
        skill_description: str,
        skill_summary: Optional[str] = None,
        use_cache: bool = True,
    ) -> List[float]:
        """
        Generate embedding for a skill.
        
        Combines name, description, and summary into a single
        text for embedding generation.
        
        Args:
            skill_name: The skill name
            skill_description: The skill description
            skill_summary: Optional skill summary
            use_cache: Whether to use cached embeddings
            
        Returns:
            The embedding vector
        """
        # Create cache key
        cache_key = f"{skill_name}:{skill_description}:{skill_summary or ''}"
        
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]
        
        # Combine text for embedding
        text_parts = [
            f"Skill: {skill_name}",
            f"Description: {skill_description}",
        ]
        if skill_summary:
            text_parts.append(f"Summary: {skill_summary}")
        
        text = "\n".join(text_parts)
        
        embedding = self.provider.get_embedding(text)
        
        if use_cache:
            self._cache[cache_key] = embedding
        
        return embedding
    
    def get_query_embedding(self, query: str) -> List[float]:
        """
        Generate embedding for a search query.
        
        Args:
            query: The search query
            
        Returns:
            The embedding vector
        """
        return self.provider.get_embedding(query)
    
    def compute_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float],
    ) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding
            embedding2: Second embedding
            
        Returns:
            Cosine similarity score (0-1)
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    def find_similar(
        self,
        query_embedding: List[float],
        candidate_embeddings: List[Tuple[str, List[float]]],
        top_k: int = 10,
        min_similarity: float = 0.0,
    ) -> List[Tuple[str, float]]:
        """
        Find most similar embeddings to a query.
        
        Args:
            query_embedding: The query embedding
            candidate_embeddings: List of (id, embedding) tuples
            top_k: Maximum results to return
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of (id, similarity) tuples, sorted by similarity
        """
        results = []
        
        for skill_id, embedding in candidate_embeddings:
            similarity = self.compute_similarity(query_embedding, embedding)
            if similarity >= min_similarity:
                results.append((skill_id, similarity))
        
        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:top_k]
    
    def batch_compute_embeddings(
        self,
        texts: List[str],
    ) -> List[List[float]]:
        """
        Compute embeddings for multiple texts in batch.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings
        """
        return self.provider.get_embeddings(texts)
    
    @property
    def model_name(self) -> str:
        """Return the embedding model name."""
        return self.provider.model_name
    
    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        return self.provider.dimension
    
    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()