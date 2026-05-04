import asyncio
import os
import sys
from pathlib import Path

import pytest

# Add the root directory to path so we can import project modules
sys.path.append(str(Path(__file__).parent.parent))

from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc

import config
import index_archive


@pytest.mark.skipif(os.environ.get("GITHUB_ACTIONS") == "true", reason="Cannot run LLM inference on GitHub Actions runners")
def test_rag_pipeline(tmp_path):
    """
    Integration test verifying the core RAG pipeline (indexing and querying) works structurally,
    without leaking state to the real knowledge_base directory.
    """
    async def run():
        # 1. State Isolation: Use tmp_path for the working directory
        working_dir = str(tmp_path)

        # 2. Setup Provider
        provider = index_archive._setup_provider()

        # 3. Initialize LightRAG
        rag = LightRAG(
            working_dir=working_dir,
            llm_model_func=provider["func"],
            llm_model_name=provider["name"],
            llm_model_max_async=provider["max_async"],
            max_total_tokens=config.LOCAL_CONTEXT_WINDOW,
            llm_model_kwargs=provider["kwargs"],
            entity_extract_max_gleaning=0,
            summary_context_size=min(6000, config.LOCAL_CONTEXT_WINDOW),
            default_embedding_timeout=120,
            embedding_func=EmbeddingFunc(
                embedding_dim=768,
                max_token_size=8192,
                func=index_archive._local_embed,
            ),
        )

        await rag.initialize_storages()

        # 4. Insert dummy document
        await rag.ainsert("The sky is blue and water is wet.")

        # 5. Run a query
        result = await rag.aquery("What color is the sky?", param=QueryParam(mode="naive"))

        # 6. Structural Assertions Only
        assert isinstance(result, str)
        assert len(result) > 0

    asyncio.run(run())
