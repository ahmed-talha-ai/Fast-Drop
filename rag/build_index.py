# rag/build_index.py
# ═══════════════════════════════════════════════════════════════════
# Bilingual RAG Builder using LlamaIndex & BM25
# ═══════════════════════════════════════════════════════════════════
import os
import json
import logging
from pathlib import Path

from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    StorageContext,
    Settings,
    load_index_from_storage,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.retrievers.bm25 import BM25Retriever
import Stemmer

logger = logging.getLogger("fastdrop.rag")

INDEX_DIR = Path("rag/index_data")
KB_DIR = Path("rag/knowledge_base")

# ── Global Cache ─────────────────────────────────────
_vector_index = None
_bm25_retriever = None

# ── Arabic Stopwords (BM25Retriever doesn't support language="arabic") ──────
ARABIC_STOPWORDS = [
    "من", "إلى", "عن", "على", "في", "هو", "هي", "هم", "نحن", "أنت",
    "ما", "لا", "إن", "أن", "كان", "كانت", "هذا", "هذه", "ذلك", "تلك",
    "مع", "كل", "بعد", "قبل", "عند", "حتى", "أو", "و", "ثم", "لكن",
    "لم", "لن", "قد", "التي", "الذي", "الذين", "التي", "به", "لها",
    "لهم", "منه", "منها", "فيه", "فيها", "عنه", "عنها", "إلا", "بل",
    "لو", "لولا", "حين", "بين", "خلال", "بدون", "رغم", "مثل", "حول",
    "يكون", "تكون", "يكن", "أكثر", "أقل", "جداً", "أيضاً", "فقط",
    "هناك", "هنا", "أين", "متى", "كيف", "لماذا", "ماذا",
]

# Configure LlamaIndex Settings
Settings.embed_model = HuggingFaceEmbedding(model_name=os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"))
Settings.node_parser = SentenceSplitter(chunk_size=1024, chunk_overlap=200)
# We handle LLM calls externally in fallback_manager, so we can disable the default LLM here
Settings.llm = None


def load_knowledge_base():
    """Load documents from rag/knowledge_base/ directory."""
    if not KB_DIR.exists():
        logger.warning(f"[RAG] Knowledge base dir not found: {KB_DIR}")
        return []

    logger.info(f"[RAG] Loading documents from: {KB_DIR}")
    reader = SimpleDirectoryReader(input_dir=str(KB_DIR), recursive=True)
    documents = reader.load_data()
    
    # Optional: You could apply normalization here if needed, 
    # but BAAI/bge-m3 handles raw Arabic quite well.
    return documents


def build_full_index():
    """
    Builds the Vector Index and BM25 Retriever from scratch.
    """
    global _vector_index, _bm25_retriever
    
    documents = load_knowledge_base()
    if not documents:
        logger.warning("[RAG] No documents loaded — RAG will be unavailable")
        return None, None

    logger.info("[RAG] Building Vector Store Index...")
    _vector_index = VectorStoreIndex.from_documents(documents)
    
    logger.info("[RAG] Building BM25 Retriever...")
    nodes = Settings.node_parser.get_nodes_from_documents(documents)
    # Arabic stemmer handles Arabic root extraction for better BM25 matching
    _bm25_retriever = BM25Retriever.from_defaults(
        nodes=nodes,
        similarity_top_k=10,
        stemmer=Stemmer.Stemmer('arabic'),
    )

    save_index()
    return _vector_index, _bm25_retriever


def save_index():
    """Save LlamaIndex and BM25 to disk."""
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save Vector Index
    if _vector_index:
        _vector_index.storage_context.persist(persist_dir=str(INDEX_DIR))
    
    # Save BM25 Retriever
    if _bm25_retriever:
        _bm25_retriever.persist(str(INDEX_DIR / "bm25_retriever.json"))
        
    logger.info(f"[RAG] Saved index and BM25 to {INDEX_DIR}")


def load_index():
    """Load persisted LlamaIndex and BM25 from disk."""
    global _vector_index, _bm25_retriever
    
    if not (INDEX_DIR / "docstore.json").exists() or not (INDEX_DIR / "bm25_retriever.json").exists():
        logger.info("[RAG] No saved index found — building from scratch")
        return build_full_index()

    try:
        logger.info("[RAG] Loading Vector Store Index from disk...")
        storage_context = StorageContext.from_defaults(persist_dir=str(INDEX_DIR))
        _vector_index = load_index_from_storage(storage_context)
        
        logger.info("[RAG] Loading BM25 Retriever from disk...")
        _bm25_retriever = BM25Retriever.from_persist_dir(str(INDEX_DIR / "bm25_retriever.json"))
        
        logger.info("[RAG] Successfully loaded indices.")
        return _vector_index, _bm25_retriever
        
    except Exception as e:
        logger.error(f"[RAG] Failed to load index: {e}. Rebuilding...")
        return build_full_index()
