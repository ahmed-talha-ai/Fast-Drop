# api/chat.py
# ═══════════════════════════════════════════════════════════
# Chat API — Bilingual NLP Chatbot endpoint
# ═══════════════════════════════════════════════════════════
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db

logger = logging.getLogger("fastdrop.api.chat")
router = APIRouter(prefix="/api/chat", tags=["Chat"])


class ChatMessage(BaseModel):
    message: str
    customer_id: int | None = None


class ChatResponse(BaseModel):
    reply: str
    detected_language: str
    intent: str | None = None


# Global RAG components (loaded at startup)
_rag_components = {"vector_index": None, "bm25_retriever": None}


def set_rag_components(vector_index, bm25_retriever):
    """Set LlamaIndex RAG components from main.py startup."""
    _rag_components["vector_index"] = vector_index
    _rag_components["bm25_retriever"] = bm25_retriever


@router.post("/", response_model=ChatResponse)
async def chat(data: ChatMessage, db: AsyncSession = Depends(get_db)):
    """
    Send a message to the bilingual AI chatbot.
    Supports: Egyptian Arabic, MSA, Arabizi, English, mixed.

    Example requests:
    - {"message": "فين الأوردر بتاعي ORD-2026-12345"}
    - {"message": "feen el order bta3y?"}
    - {"message": "What are your delivery fees?"}
    """
    from ai.nlp_chatbot import handle_chat_bilingual, classify_intent_bilingual
    from core.arabic_normalizer import prepare_user_input

    # Preprocess to detect language
    meta = prepare_user_input(data.message)

    # Classify intent first (for metadata in response)
    intent_str = None
    try:
        intent_data = classify_intent_bilingual(data.message, meta)
        intent_str = intent_data.get("intent")
    except Exception:
        pass

    reply = await handle_chat_bilingual(
        raw_user_msg=data.message,
        db_session=db,
        vector_index=_rag_components["vector_index"],
        bm25_retriever=_rag_components["bm25_retriever"],
    )

    return ChatResponse(
        reply=reply,
        detected_language=meta["input_type"],
        intent=intent_str,
    )
