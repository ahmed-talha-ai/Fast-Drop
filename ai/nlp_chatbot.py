# ai/nlp_chatbot.py
# ═══════════════════════════════════════════════════════════════════
# Bilingual NLP Chatbot — Egyptian Arabic + English
# Intent Classification → RAG → Response Generation
# Primary: Groq Llama 4 Maverick (official Arabic support)
# ═══════════════════════════════════════════════════════════════════
import json
import logging
from langsmith import traceable

logger = logging.getLogger("fastdrop.chatbot")

# ═══════════════════════════════════════════════
# Bilingual Intent Classification System Prompt
# ═══════════════════════════════════════════════
BILINGUAL_INTENT_PROMPT = """
You are an intent classifier for Fast Drop (فاست دروب),
an Egyptian delivery company. Users write in Egyptian Arabic dialect,
Modern Standard Arabic, Franco-Arabic (Arabizi like "feen el order"),
English, or a mixture of all of these.

Classify the input into EXACTLY ONE intent:

  - track_order: user asks about the STATUS, LOCATION, or ETA of a SPECIFIC existing order they placed.
    (Arabic: فين, وصل, الشحنة, الطرد, تتبع)
    (English: "where is my order", "track my order", "has it arrived", "when will it arrive", "order status")
    ⚠️ ONLY use when user is asking about a SPECIFIC order. NOT for general pricing questions.

  - change_address: user wants to update the delivery address of an order.
    (Arabic: عنوان, غير العنوان, بدل, تعديل)
    (English: "change address", "update address", "different location", "new address")

  - reschedule: user wants the delivery at a different time or date.
    (Arabic: موعد, وقت, تأجيل, بكرة, اجيل)
    (English: "reschedule", "change time", "deliver tomorrow", "different day", "later")

  - cancel_order: user wants to cancel their order entirely.
    (Arabic: الغي, إلغاء, مش عاوزه, كنسل, بطل)
    (English: "cancel", "cancel my order", "don't want it", "stop the delivery")

  - complaint: damage, theft, wrong item, driver behavior issue, or very late delivery.
    (Arabic: اتكسر, اتسرق, مش تمام, وحش, متأخر جداً, شكوى, مشكلة)
    (English: "broken", "damaged", "stolen", "wrong item", "bad driver", "very late", "complaint", "problem with order")

  - policy_query: general questions about PRICING, FEES, COVERAGE ZONES, DELIVERY AREAS, or SERVICE POLICIES.
    (Arabic: رسوم, بكام, التعرفة, السعر, مناطق, إرجاع, ساعات العمل, بيشتغلوا, تكلف كام)
    (English: "fees", "price", "how much", "cost", "delivery fee", "delivery charge",
              "zones", "areas", "do you deliver to", "working hours", "return policy", "what areas")
    ⚠️ Use this for ANY general service/pricing question — NOT about a specific placed order.

  - other: greetings, thanks, or anything else.

Extract entities if present:
  - order_id: numeric ID or Arabic order reference
  - address: any delivery address mentioned
  - date_time: any time or date expression (النهارده, بكرة, etc.)

Respond ONLY with valid JSON:
{
  "intent": "<intent>",
  "confidence": <0.0-1.0>,
  "entities": {
    "order_id": "<id or null>",
    "address": "<address or null>",
    "date_time": "<expression or null>"
  },
  "detected_language": "<ar_dialect | ar_msa | arabizi | en | mixed>"
}
"""


# ═══════════════════════════════════════════════
# Arabic Response System Prompts
# ═══════════════════════════════════════════════
ARABIC_RESPONSE_SYSTEM = (
    "أنت موظف خدمة عملاء في شركة Fast Drop للتوصيل في مصر. "
    "ردودك دايماً تكون بالعربية المصرية العامية — مش فصحى رسمية. "
    "لهجتك ودية وقريبة ومحترمة زي أي موظف مصري محترف. "
    "لو الزبون كتب بالعربي أو عربيزي، رد بالعربي المصري العامي. "
    "لو الزبون كتب بالإنجليزي، رد بالإنجليزي. "
    "الرد يكون قصير ومفيد — مش أكتر من 3 جمل."
)

ENGLISH_RESPONSE_SYSTEM = (
    "You are a customer service agent for Fast Drop delivery in Egypt. "
    "Be warm, professional, and concise (max 2-3 sentences). "
    "If the customer wrote in Arabic/Arabizi, respond in Egyptian Arabic dialect. "
    "If they wrote in English, respond in clear friendly English."
)


@traceable(run_type="chain", name="Intent_Classification")
def classify_intent_bilingual(user_msg: str, input_metadata: dict) -> dict:
    """
    Intent classification using Llama 4 Maverick (official Arabic).
    Falls back through Groq → Gemini → OpenRouter chain.
    """
    from ai.fallback_manager import call_gemini_with_fallback

    messages = [
        {"role": "system", "content": BILINGUAL_INTENT_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    result = call_gemini_with_fallback(
        messages=messages,
        temperature=0.0,
        json_response=True,
        preferred_model="gemini-2.5-flash",
    )
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code block (```json ... ```)
        import re as _re
        match = _re.search(r'```(?:json)?\s*({.*?})\s*```', result, _re.DOTALL)
        if not match:
            # Try any JSON object in the response
            match = _re.search(r'(\{[^{}]*"intent"[^{}]*\})', result, _re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return {
            "intent": "other",
            "confidence": 0.0,
            "entities": {"order_id": None, "address": None, "date_time": None},
            "detected_language": input_metadata.get("input_type", "unknown"),
        }


# ═══════════════════════════════════════════════
# CRAG: Corrective RAG Quality Check
# ═══════════════════════════════════════════════
def assess_retrieval_quality(query: str, chunks: list) -> str:
    """
    CRAG pattern: Evaluate if retrieved chunks actually answer the query.
    Returns: "correct" | "ambiguous" | "wrong"
    """
    if not chunks:
        return "wrong"

    from ai.fallback_manager import call_gemini_with_fallback

    # LlamaIndex nodes store their text in .get_content() but just in case
    # we handle both dict.get("text") and node.get_content() formats
    context = ""
    for c in chunks[:3]:
        if hasattr(c, "node"):
            context += c.node.get_content() + "\n"
        elif isinstance(c, dict):
            context += c.get("text", str(c)) + "\n"
        else:
            context += str(c) + "\n"

    messages = [
        {
            "role": "user",
            "content": (
                f"هل هذا السياق يحتوي على أي معلومات مفيدة أو متعلقة من قريب أو من بعيد بالسؤال؟ إذا نعم، قم بتقييمه كـ 'correct'.\n"
                f"إذا كان السياق لا يمت بصلة تماماً للسؤال، قم بتقييمه كـ 'wrong'.\n"
                f"السؤال: {query}\n"
                f"السياق: {context}\n"
                'Respond ONLY in valid JSON format: {"quality": "correct|ambiguous|wrong"}\n'
                'Ensure the response is exactly this json object.'
            ),
        }
    ]
    result = call_gemini_with_fallback(
        messages=messages,
        temperature=0.0,
        json_response=True,
        preferred_model="gemini-2.5-flash",
    )
    try:
        return json.loads(result).get("quality", "ambiguous")
    except Exception:
        return "ambiguous"


# ═══════════════════════════════════════════════
# Arabic Response Generator
# ═══════════════════════════════════════════════
def generate_tracking_response(order_data: dict, response_language: str) -> str:
    """Generate natural-language order status in matching language."""
    from ai.fallback_manager import call_gemini_with_fallback
    from core.arabic_normalizer import arabic_status

    if response_language == "ar":
        system = ARABIC_RESPONSE_SYSTEM
        user_content = (
            "اكتب رد طبيعي على الزبون عن حالة الأوردر بتاعه.\n"
            f"البيانات:\n"
            f"- رقم الأوردر: {order_data['id']}\n"
            f"- الحالة: {arabic_status(order_data['status'])}\n"
            f"- المنطقة: {order_data.get('zone', 'غير محدد')}\n"
            f"- الموعد المتوقع: {order_data.get('eta', 'لسه اتحدد')}\n"
            f"- اسم الديليفري بوي: {order_data.get('driver_name', 'لسه اتحدد')}\n"
            "الرد بالعربي المصري العامي — قصير ومفيد."
        )
    else:
        system = ENGLISH_RESPONSE_SYSTEM
        user_content = (
            f"Write a friendly 2-sentence delivery status update.\n"
            f"Order: #{order_data['id']}, Status: {order_data['status']}, "
            f"Zone: {order_data.get('zone', 'N/A')}, "
            f"ETA: {order_data.get('eta', 'TBD')}."
        )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
    return call_gemini_with_fallback(
        messages=messages,
        temperature=0.7,
        preferred_model="gemini-2.5-flash",
    )


# ═══════════════════════════════════════════════
# Bilingual RAG Query Handler
# ═══════════════════════════════════════════════
@traceable(run_type="chain", name="RAG_Retrieval_Chain")
async def handle_rag_query_bilingual(
    query: str,
    vector_index,
    bm25_retriever,
    response_lang: str = "ar",
) -> str:
    """RAG pipeline using LlamaIndex QueryFusionRetriever."""
    from ai.fallback_manager import call_gemini_with_fallback
    from llama_index.core.retrievers import QueryFusionRetriever

    # Check semantic cache
    try:
        from rag.rag_cache import cache_get, cache_set
        cached = cache_get(query)
        if cached:
            return cached
    except Exception:
        pass

    # Hybrid retrieval setup
    try:
        # Get dense retriever from index
        if vector_index and bm25_retriever:
            vector_retriever = vector_index.as_retriever(similarity_top_k=15)
            
            # Fuse both retrievers using LlamaIndex QueryFusionRetriever (native RRF)
            fused_retriever = QueryFusionRetriever(
                [vector_retriever, bm25_retriever],
                similarity_top_k=5,
                num_queries=1,  # Simple RRF without rewriting for speed
                mode="reciprocal_rerank",
                use_async=False,
            )
            top_nodes = fused_retriever.retrieve(query)
        else:
            top_nodes = []
    except Exception as e:
        logger.error(f"[RAG] Fusion retrieval error: {e}")
        top_nodes = []

    if not top_nodes:
        return (
            "مش لاقي إجابة لسؤالك في قاعدة المعرفة بتاعتنا. تواصل معانا على support@fastdrop.eg"
            if response_lang == "ar"
            else "I couldn't find an answer. Contact support@fastdrop.eg"
        )

    # CRAG quality check with Llama-3.3 Judge
    quality = assess_retrieval_quality(query, top_nodes)
    if quality == "wrong":
        logger.info(f"[RAG] CRAG marked context as wrong for query: {query}")
        return (
            "مش لاقي إجابة لسؤالك في قاعدة المعرفة بتاعتنا. تواصل معانا على support@fastdrop.eg"
            if response_lang == "ar"
            else "I couldn't find an answer. Contact support@fastdrop.eg"
        )

    context = "\n\n".join([n.node.get_content() for n in top_nodes])

    # Generate response
    if response_lang == "ar":
        prompt = (
            "أنت موظف خدمة عملاء في Fast Drop.\n"
            "بس بالعربي المصري العامي باستخدام المعلومات دي بس أجب على السؤال.\n"
            "لو المعلومات مش كافية قول كده بدون اختراع.\n"
            f"المعلومات:\n{context}\n\n"
            f"السؤال: {query}\n"
            "الرد بالعربي المصري:"
        )
    else:
        prompt = (
            f"Answer using ONLY the provided context. If insufficient, say so.\n"
            f"Context: {context}\n\n"
            f"Question: {query}"
        )

    messages = [{"role": "user", "content": prompt}]
    answer = call_gemini_with_fallback(
        messages=messages,
        temperature=0.3,
        preferred_model="gemini-2.5-flash",
    )

    # Cache result
    try:
        from rag.rag_cache import cache_set
        cache_set(query, answer)
    except Exception:
        pass

    return answer


# ═══════════════════════════════════════════════
# Full Bilingual Chat Orchestrator
# ═══════════════════════════════════════════════
@traceable(run_type="chain", name="Main_Chat_Orchestrator")
async def handle_chat_bilingual(
    raw_user_msg: str,
    db_session,
    vector_index=None,
    bm25_retriever=None,
) -> str:
    """
    Complete chat pipeline:
    1. Preprocess (CAMeL Tools)
    2. Classify intent (Llama 4 Maverick)
    3. Route to handler
    4. Generate response in matching language
    """
    from core.arabic_normalizer import prepare_user_input

    # ── Step 1: Preprocess ────────────────────────────
    meta = prepare_user_input(raw_user_msg)
    normalized_msg = meta["normalized"]
    response_lang = meta["response_language"]

    # ── Step 2: Classify intent ───────────────────────
    intent_data = classify_intent_bilingual(normalized_msg, meta)
    intent = intent_data.get("intent", "other")
    order_id = intent_data.get("entities", {}).get("order_id")

    # ── Step 3: Route to handler ──────────────────────
    if intent == "track_order":
        if not order_id:
            return (
                "من فضلك ادي رقم الأوردر بتاعك عشان أقدر أساعدك! 🚚"
                if response_lang == "ar"
                else "Please share your order ID and I'll check right away!"
            )

        # Query DB for order
        try:
            from models import Order
            from sqlalchemy import select

            result = await db_session.execute(
                select(Order).where(Order.id == order_id)
            )
            order = result.scalar_one_or_none()

            if not order:
                return (
                    "مش لاقي أوردر بالرقم ده. تأكد من الرقم وحاول تاني."
                    if response_lang == "ar"
                    else f"Order #{order_id} not found. Please verify the ID."
                )

            return generate_tracking_response(
                {
                    "id": order.id,
                    "status": order.status.value if hasattr(order.status, "value") else str(order.status),
                    "zone": "القاهرة",
                    "eta": str(order.eta) if order.eta else "لسه اتحدد",
                    "driver_name": None,
                },
                response_lang,
            )
        except Exception as e:
            logger.error(f"DB query error: {e}")
            return (
                "حصل مشكلة في البحث عن الأوردر. حاول تاني كمان شوية."
                if response_lang == "ar"
                else "There was an error looking up your order. Please try again."
            )

    elif intent == "change_address":
        new_addr = intent_data.get("entities", {}).get("address")
        if new_addr and order_id:
            return (
                f"تمام! هنحدث عنوان التوصيل للأوردر #{order_id} للعنوان الجديد. ده ممكن يأثر على وقت التوصيل."
                if response_lang == "ar"
                else f"Got it! Updating delivery address for order #{order_id}."
            )
        return (
            "اديني رقم الأوردر والعنوان الجديد وهحدثه فوراً."
            if response_lang == "ar"
            else "Please share the order ID and new address."
        )

    elif intent == "cancel_order":
        if not order_id:
            return (
                "عشان ألغي الأوردر، محتاج أعرف رقم الأوردر بتاعك من فضلك."
                if response_lang == "ar"
                else "To cancel your order, please provide the order ID."
            )
        try:
            from models import Order, OrderStatus
            from sqlalchemy import select

            result = await db_session.execute(
                select(Order).where(Order.id == order_id)
            )
            order = result.scalar_one_or_none()

            if not order:
                return (
                    "مش لاقي أوردر بالرقم ده. تأكد من الرقم وحاول تاني."
                    if response_lang == "ar"
                    else f"Order #{order_id} not found. Please verify the ID."
                )

            if order.status in [OrderStatus.Delivered, OrderStatus.Failed, OrderStatus.Cancelled]:
                return (
                    f"الأوردر ده حالته الفعلية ({order.status.value}) ومينفعش يتلغي دلوقتي."
                    if response_lang == "ar"
                    else f"This order cannot be cancelled as its status is {order.status.value}."
                )

            order.status = OrderStatus.Cancelled
            await db_session.commit()
            return (
                f"تم إلغاء أوردر #{order_id} بنجاح بناءً على طلبك. لو احتجت أي حاجة تانية أنا موجود."
                if response_lang == "ar"
                else f"Order #{order_id} has been successfully cancelled. Let me know if you need anything else."
            )
        except Exception as e:
            logger.error(f"DB cancellation error: {e}")
            return (
                "حصل مشكلة وأنا بحاول ألغي الأوردر. تواصل مع خدمة العملاء."
                if response_lang == "ar"
                else "An error occurred while trying to cancel your order. Please contact support."
            )

    elif intent == "complaint":
        return (
            f"أنا آسف جداً على الإزعاج! هحول شكواك لمشرف دلوقتي.\nرقم مرجعي: {order_id or 'جاري التحديد'}"
            if response_lang == "ar"
            else "I'm very sorry! Connecting you with a supervisor now."
        )

    elif intent == "reschedule":
        date_time = intent_data.get("entities", {}).get("date_time")
        return (
            f"تمام! هنحاول نأجل التوصيل {'ل' + date_time if date_time else 'لموعد تاني'}. "
            "ادي رقم الأوردر لو مديتهوش."
            if response_lang == "ar"
            else f"Sure! We'll try to reschedule {'to ' + date_time if date_time else 'for another time'}."
        )

    elif intent == "policy_query":
        # ── Updated from FAISS 'faiss_index, chunks, bm25' to LlamaIndex native components ──
        if vector_index and bm25_retriever:
            return await handle_rag_query_bilingual(
                normalized_msg, vector_index, bm25_retriever, response_lang
            )
        # Fallback without RAG
        from ai.fallback_manager import call_groq_with_fallback
        return call_groq_with_fallback(
            messages=[
                {"role": "system", "content": ARABIC_RESPONSE_SYSTEM if response_lang == "ar" else ENGLISH_RESPONSE_SYSTEM},
                {"role": "user", "content": normalized_msg},
            ],
            temperature=0.5,
            max_tokens=200,
            arabic_mode=(response_lang == "ar"),
        )

    # Default fallback
    return (
        "ازاي أقدر أساعدك النهارده؟ اسألني عن أوردرك أو أي حاجة تانية."
        if response_lang == "ar"
        else "How can I help you today? Ask about your order or our services."
    )
