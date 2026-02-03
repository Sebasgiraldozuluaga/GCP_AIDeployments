"""
Hugging Face Tools for Google ADK Agent
Provides HF Hub search and exploration capabilities as agent tools
"""

import json
import logging
import time
from functools import lru_cache
from typing import Optional

from app.hf_mcp_client import get_hf_client

logger = logging.getLogger(__name__)

# ============================================
# Cache Configuration
# ============================================
CACHE_TTL_SECONDS = 300  # 5 minutes TTL for search results
CACHE_MAX_SIZE = 128  # Max cached entries


def _get_cache_key_time_bucket() -> int:
    """Get time bucket for TTL-based cache invalidation (5 min buckets)."""
    return int(time.time() // CACHE_TTL_SECONDS)


@lru_cache(maxsize=CACHE_MAX_SIZE)
def _cached_search_models(
    query: str,
    limit: int,
    task: Optional[str],
    library: Optional[str],
    _time_bucket: int  # For TTL invalidation
) -> dict:
    """Cached version of model search."""
    client = get_hf_client()
    return client.search_models(
        query=query,
        limit=limit,
        filter_task=task,
        filter_library=library
    )


@lru_cache(maxsize=CACHE_MAX_SIZE)
def _cached_search_datasets(
    query: str,
    limit: int,
    task: Optional[str],
    _time_bucket: int
) -> dict:
    """Cached version of dataset search."""
    client = get_hf_client()
    return client.search_datasets(
        query=query,
        limit=limit,
        filter_task=task
    )


@lru_cache(maxsize=CACHE_MAX_SIZE)
def _cached_search_spaces(
    query: str,
    limit: int,
    sdk: Optional[str],
    _time_bucket: int
) -> dict:
    """Cached version of spaces search."""
    client = get_hf_client()
    return client.search_spaces(
        query=query,
        limit=limit,
        filter_sdk=sdk
    )


@lru_cache(maxsize=64)
def _cached_model_info(model_id: str, _time_bucket: int) -> dict:
    """Cached version of model info."""
    client = get_hf_client()
    return client.get_model_info(model_id)


@lru_cache(maxsize=64)
def _cached_dataset_info(dataset_id: str, _time_bucket: int) -> dict:
    """Cached version of dataset info."""
    client = get_hf_client()
    return client.get_dataset_info(dataset_id)


def search_hf_models(
    query: str,
    limit: int = 5,
    task: Optional[str] = None,
    library: Optional[str] = None
) -> str:
    """
    Search for AI models on Hugging Face Hub.

    Use this tool to find pre-trained models, transformers, diffusion models, and other
    ML models. Results include model cards, download counts, and usage information.

    Args:
        query: Search query (e.g., "sentiment analysis", "image generation", "llama")
        limit: Maximum number of results to return (default: 5, max: 20)
        task: Filter by task type (e.g., "text-classification", "text-generation",
              "image-to-text", "text-to-image", "translation")
        library: Filter by library (e.g., "transformers", "diffusers", "sentence-transformers")

    Returns:
        JSON string with model search results including:
        - Model ID and name
        - Description
        - Downloads count
        - Likes count
        - Tasks/pipeline tags
        - Library information
        - Direct link to model card

    Examples:
        search_hf_models("spanish sentiment analysis")
        search_hf_models("stable diffusion", task="text-to-image")
        search_hf_models("llama", library="transformers", limit=10)
    """
    try:
        # Validate and cap limit
        limit = min(max(1, limit), 20)

        # Call cached search (TTL-based invalidation)
        time_bucket = _get_cache_key_time_bucket()
        result = _cached_search_models(
            query=query,
            limit=limit,
            task=task,
            library=library,
            _time_bucket=time_bucket
        )

        # Format results for agent
        if result["success"]:
            models = result.get("models", [])
            formatted = []

            for model in models:
                formatted.append({
                    "id": model.get("id", ""),
                    "name": model.get("modelId", model.get("id", "")),
                    "description": model.get("cardData", {}).get("description", "No description")[:200],
                    "downloads": model.get("downloads", 0),
                    "likes": model.get("likes", 0),
                    "tasks": model.get("pipeline_tag", ""),
                    "library": model.get("library_name", ""),
                    "url": f"https://huggingface.co/{model.get('id', '')}"
                })

            return json.dumps({
                "success": True,
                "count": len(formatted),
                "query": query,
                "models": formatted
            }, indent=2, ensure_ascii=False)
        else:
            return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error in search_hf_models: {e}", exc_info=True)
        return json.dumps({
            "success": False,
            "error": str(e),
            "query": query
        })


def search_hf_datasets(
    query: str,
    limit: int = 5,
    task: Optional[str] = None
) -> str:
    """
    Search for datasets on Hugging Face Hub.

    Use this tool to find training data, evaluation benchmarks, and datasets
    for machine learning tasks.

    Args:
        query: Search query (e.g., "spanish text", "image classification", "qa")
        limit: Maximum number of results to return (default: 5, max: 20)
        task: Filter by task category (e.g., "text-classification", "question-answering",
              "translation", "image-classification")

    Returns:
        JSON string with dataset search results including:
        - Dataset ID and name
        - Description
        - Downloads count
        - Likes count
        - Task categories
        - Size information
        - Direct link to dataset

    Examples:
        search_hf_datasets("spanish news articles")
        search_hf_datasets("medical imaging", task="image-classification")
        search_hf_datasets("qa benchmark", limit=10)
    """
    try:
        limit = min(max(1, limit), 20)

        # Call cached search (TTL-based invalidation)
        time_bucket = _get_cache_key_time_bucket()
        result = _cached_search_datasets(
            query=query,
            limit=limit,
            task=task,
            _time_bucket=time_bucket
        )

        if result["success"]:
            datasets = result.get("datasets", [])
            formatted = []

            for dataset in datasets:
                formatted.append({
                    "id": dataset.get("id", ""),
                    "name": dataset.get("id", "").split("/")[-1],
                    "description": dataset.get("cardData", {}).get("description", "No description")[:200],
                    "downloads": dataset.get("downloads", 0),
                    "likes": dataset.get("likes", 0),
                    "tasks": dataset.get("tags", []),
                    "url": f"https://huggingface.co/datasets/{dataset.get('id', '')}"
                })

            return json.dumps({
                "success": True,
                "count": len(formatted),
                "query": query,
                "datasets": formatted
            }, indent=2, ensure_ascii=False)
        else:
            return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error in search_hf_datasets: {e}", exc_info=True)
        return json.dumps({
            "success": False,
            "error": str(e),
            "query": query
        })


def search_hf_spaces(
    query: str,
    limit: int = 5,
    sdk: Optional[str] = None
) -> str:
    """
    Search for Spaces (interactive ML apps and demos) on Hugging Face Hub.

    Use this tool to find Gradio/Streamlit apps, interactive demos, and ML applications
    that you can reference or explore.

    Args:
        query: Search query (e.g., "chatbot", "image generation", "transcription")
        limit: Maximum number of results to return (default: 5, max: 20)
        sdk: Filter by SDK type ("gradio", "streamlit", "docker", "static")

    Returns:
        JSON string with Spaces search results including:
        - Space ID and name
        - Description
        - SDK type (Gradio, Streamlit, etc.)
        - Likes count
        - Direct link to Space

    Examples:
        search_hf_spaces("text to speech")
        search_hf_spaces("chatbot", sdk="gradio")
        search_hf_spaces("stable diffusion demo", limit=10)
    """
    try:
        limit = min(max(1, limit), 20)

        # Call cached search (TTL-based invalidation)
        time_bucket = _get_cache_key_time_bucket()
        result = _cached_search_spaces(
            query=query,
            limit=limit,
            sdk=sdk,
            _time_bucket=time_bucket
        )

        if result["success"]:
            spaces = result.get("spaces", [])
            formatted = []

            for space in spaces:
                formatted.append({
                    "id": space.get("id", ""),
                    "name": space.get("id", "").split("/")[-1],
                    "description": space.get("cardData", {}).get("description", "No description")[:200],
                    "sdk": space.get("sdk", "unknown"),
                    "likes": space.get("likes", 0),
                    "url": f"https://huggingface.co/spaces/{space.get('id', '')}"
                })

            return json.dumps({
                "success": True,
                "count": len(formatted),
                "query": query,
                "spaces": formatted
            }, indent=2, ensure_ascii=False)
        else:
            return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error in search_hf_spaces: {e}", exc_info=True)
        return json.dumps({
            "success": False,
            "error": str(e),
            "query": query
        })


def get_hf_model_details(model_id: str) -> str:
    """
    Get detailed information about a specific Hugging Face model.

    Use this tool when you need complete information about a model including
    its capabilities, usage examples, training data, and technical specifications.

    Args:
        model_id: Full model identifier (e.g., "meta-llama/Llama-2-7b-hf",
                  "stabilityai/stable-diffusion-xl-base-1.0")

    Returns:
        JSON string with detailed model information including:
        - Full model card
        - Training details
        - Usage examples
        - Model architecture
        - License information
        - Performance metrics
        - Required libraries

    Example:
        get_hf_model_details("bert-base-uncased")
    """
    try:
        # Call cached model info (TTL-based invalidation)
        time_bucket = _get_cache_key_time_bucket()
        result = _cached_model_info(model_id, time_bucket)
        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Error in get_hf_model_details: {e}", exc_info=True)
        return json.dumps({
            "success": False,
            "error": str(e),
            "model_id": model_id
        })


def get_hf_dataset_details(dataset_id: str) -> str:
    """
    Get detailed information about a specific Hugging Face dataset.

    Use this tool when you need complete information about a dataset including
    its structure, size, splits, and usage examples.

    Args:
        dataset_id: Full dataset identifier (e.g., "squad", "wikitext",
                    "wikipedia/20220301.en")

    Returns:
        JSON string with detailed dataset information including:
        - Dataset card
        - Size and splits
        - Features/columns
        - Usage examples
        - License information
        - Citation information

    Example:
        get_hf_dataset_details("squad")
    """
    try:
        # Call cached dataset info (TTL-based invalidation)
        time_bucket = _get_cache_key_time_bucket()
        result = _cached_dataset_info(dataset_id, time_bucket)
        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Error in get_hf_dataset_details: {e}", exc_info=True)
        return json.dumps({
            "success": False,
            "error": str(e),
            "dataset_id": dataset_id
        })
