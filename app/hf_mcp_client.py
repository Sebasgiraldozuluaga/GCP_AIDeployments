"""
Hugging Face MCP Client
Provides integration with Hugging Face Hub via Model Context Protocol (MCP)
"""

import os
import logging
import httpx
from typing import Optional, Dict, Any, List
from enum import Enum

logger = logging.getLogger(__name__)


class HFResourceType(Enum):
    """Hugging Face resource types"""
    MODEL = "model"
    DATASET = "dataset"
    SPACE = "space"
    PAPER = "paper"


class HuggingFaceMCPClient:
    """
    Client for interacting with Hugging Face MCP Server.

    This client provides access to Hugging Face Hub resources including:
    - Models: Search and explore ML models
    - Datasets: Find and analyze datasets
    - Spaces: Interact with Gradio apps and demos
    - Papers: Access research papers
    """

    def __init__(
        self,
        base_url: str = "https://huggingface.co/mcp",
        token: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize Hugging Face MCP Client.

        Args:
            base_url: Base URL for HF MCP server
            token: Hugging Face API token (from HF_TOKEN env var if not provided)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.token = token or os.getenv("HF_TOKEN")
        self.timeout = timeout

        # Set up HTTP client with auth headers
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers=headers,
            follow_redirects=True
        )

        logger.info(f"Initialized HF MCP Client with base URL: {self.base_url}")

    async def search_models(
        self,
        query: str,
        limit: int = 10,
        filter_task: Optional[str] = None,
        filter_library: Optional[str] = None,
        sort: str = "downloads"
    ) -> Dict[str, Any]:
        """
        Search for models on Hugging Face Hub.

        Args:
            query: Search query string
            limit: Maximum number of results (default: 10)
            filter_task: Filter by task (e.g., "text-classification", "text-generation")
            filter_library: Filter by library (e.g., "transformers", "diffusers")
            sort: Sort by field (downloads, likes, trending)

        Returns:
            Dictionary with search results
        """
        try:
            params = {
                "search": query,
                "limit": limit,
                "sort": sort
            }
            if filter_task:
                params["filter"] = f"task:{filter_task}"
            if filter_library:
                params["library"] = filter_library

            response = await self.client.get(
                f"https://huggingface.co/api/models",
                params=params
            )
            response.raise_for_status()

            models = response.json()
            return {
                "success": True,
                "count": len(models),
                "models": models[:limit],
                "query": query
            }

        except Exception as e:
            logger.error(f"Error searching models: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }

    async def search_datasets(
        self,
        query: str,
        limit: int = 10,
        filter_task: Optional[str] = None,
        sort: str = "downloads"
    ) -> Dict[str, Any]:
        """
        Search for datasets on Hugging Face Hub.

        Args:
            query: Search query string
            limit: Maximum number of results
            filter_task: Filter by task category
            sort: Sort by field

        Returns:
            Dictionary with search results
        """
        try:
            params = {
                "search": query,
                "limit": limit,
                "sort": sort
            }
            if filter_task:
                params["filter"] = f"task:{filter_task}"

            response = await self.client.get(
                f"https://huggingface.co/api/datasets",
                params=params
            )
            response.raise_for_status()

            datasets = response.json()
            return {
                "success": True,
                "count": len(datasets),
                "datasets": datasets[:limit],
                "query": query
            }

        except Exception as e:
            logger.error(f"Error searching datasets: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }

    async def search_spaces(
        self,
        query: str,
        limit: int = 10,
        filter_sdk: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for Spaces (Gradio/Streamlit apps) on Hugging Face Hub.

        Args:
            query: Search query string
            limit: Maximum number of results
            filter_sdk: Filter by SDK (gradio, streamlit, docker, static)

        Returns:
            Dictionary with search results
        """
        try:
            params = {
                "search": query,
                "limit": limit
            }
            if filter_sdk:
                params["filter"] = f"sdk:{filter_sdk}"

            response = await self.client.get(
                f"https://huggingface.co/api/spaces",
                params=params
            )
            response.raise_for_status()

            spaces = response.json()
            return {
                "success": True,
                "count": len(spaces),
                "spaces": spaces[:limit],
                "query": query
            }

        except Exception as e:
            logger.error(f"Error searching spaces: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }

    async def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific model.

        Args:
            model_id: Model identifier (e.g., "meta-llama/Llama-2-7b-hf")

        Returns:
            Dictionary with model information
        """
        try:
            response = await self.client.get(
                f"https://huggingface.co/api/models/{model_id}"
            )
            response.raise_for_status()

            info = response.json()
            return {
                "success": True,
                "model_id": model_id,
                "info": info
            }

        except Exception as e:
            logger.error(f"Error getting model info for {model_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "model_id": model_id
            }

    async def get_dataset_info(self, dataset_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific dataset.

        Args:
            dataset_id: Dataset identifier (e.g., "squad")

        Returns:
            Dictionary with dataset information
        """
        try:
            response = await self.client.get(
                f"https://huggingface.co/api/datasets/{dataset_id}"
            )
            response.raise_for_status()

            info = response.json()
            return {
                "success": True,
                "dataset_id": dataset_id,
                "info": info
            }

        except Exception as e:
            logger.error(f"Error getting dataset info for {dataset_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "dataset_id": dataset_id
            }

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()


# Global client instance (lazy initialization)
_hf_client: Optional[HuggingFaceMCPClient] = None


def get_hf_client() -> HuggingFaceMCPClient:
    """
    Get or create the global HF MCP client instance.

    Returns:
        HuggingFaceMCPClient instance
    """
    global _hf_client
    if _hf_client is None:
        _hf_client = HuggingFaceMCPClient()
    return _hf_client
