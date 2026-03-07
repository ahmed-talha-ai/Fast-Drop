# ai/analytics_agent.py
# ═══════════════════════════════════════════════════════════════════
# Text-to-SQL Analytics Agent — Bilingual (Arabic + English)
# Gemini Flash for SQL generation (1M token context for full schema)
# Generate → Execute → Interpret pipeline
# ═══════════════════════════════════════════════════════════════════
import json
import logging
import pandas as pd
from sqlalchemy import text as sql_text

logger = logging.getLogger("fastdrop.analytics")

FORBIDDEN_SQL = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "CREATE"]

# ═══════════════════════════════════════════════
# Bilingual Text-to-SQL Prompt
# ═══════════════════════════════════════════════
TEXT_TO_SQL_PROMPT = """
You are a senior data analyst for Fast Drop (شركة فاست دروب),
an Egyptian delivery company. Convert the question to PostgreSQL.

RULES:
- READ-ONLY queries only. Never write DROP/DELETE/UPDATE/INSERT.
- "تأخير / delays" = actual arrival > estimated arrival (compare timestamps)
- "مدينة نصر / Nasr City / نصر" = zone name_ar ILIKE '%%نصر%%' OR name_en ILIKE '%%nasr%%'
- "الأسبوع ده / this week" = current ISO week
- "امبارح / yesterday" = CURRENT_DATE - 1
- "النهارده / today" = CURRENT_DATE
- Zone names in DB may be in Arabic or English — use ILIKE for both
- Numbers may be in Arabic-Indic (٣) or Western (3) — normalize them
- Always use table aliases for clarity
- Return COUNT, SUM, AVG aggregations when asking about volume/totals

DATABASE SCHEMA:
{schema}

QUESTION: {question}
Return ONLY the SQL query — no explanation, no markdown fences.
"""


def _inspect_schema_sync(sync_conn) -> str:
    """Internal sync helper for schema extraction."""
    from sqlalchemy import inspect
    
    inspector = inspect(sync_conn)
    parts = []
    for tbl in inspector.get_table_names():
        cols = ", ".join(
            f'{c["name"]} ({c["type"]})' for c in inspector.get_columns(tbl)
        )
        parts.append(f"Table: {tbl}\nColumns: {cols}")
    return "\n\n".join(parts)


async def get_schema_text(engine) -> str:
    """Extract database schema for LLM context (Async safe)."""
    if not engine:
        return "Tables: orders, customers, drivers, zones, shipments, delivery_attempts"
        
    async with engine.connect() as conn:
        schema = await conn.run_sync(_inspect_schema_sync)
        return schema


def question_to_sql(question: str, schema: str) -> str:
    """Convert natural language question to SQL using Gemini."""
    from ai.fallback_manager import call_gemini_with_fallback

    prompt = TEXT_TO_SQL_PROMPT.format(schema=schema, question=question)

    sql = call_gemini_with_fallback(
        prompt,
        temperature=0.0,
        preferred_model="gemini-2.5-flash-lite",
    )
    # Clean response
    sql = sql.replace("```sql", "").replace("```", "").strip()
    # Remove any leading/trailing semicolons or whitespace
    sql = sql.strip().rstrip(";")
    return sql


def validate_sql(sql: str) -> bool:
    """Check SQL is safe to execute (read-only) using word boundaries."""
    import re
    sql_upper = sql.upper()
    for keyword in FORBIDDEN_SQL:
        # Use regex to match only as a full word (\b)
        pattern = rf"\b{keyword}\b"
        if re.search(pattern, sql_upper):
            logger.warning(f"[Analytics] Blocked unsafe SQL keyword: {keyword}")
            return False
    return True


async def execute_sql(sql: str, db_session) -> pd.DataFrame:
    """Execute validated SQL and return as DataFrame."""
    if not validate_sql(sql):
        raise ValueError(f"Blocked unsafe SQL: {sql[:80]}")

    result = await db_session.execute(sql_text(sql))
    rows = result.fetchall()
    columns = result.keys()
    return pd.DataFrame(rows, columns=columns)


def generate_insight(
    question: str, df: pd.DataFrame, response_lang: str = "ar"
) -> str:
    """Generate business insight from query results."""
    from ai.fallback_manager import call_gemini_with_fallback, call_groq_with_fallback

    data_md = df.head(20).to_markdown(index=False)

    if response_lang == "ar":
        prompt = (
            "أنت محلل بيانات في Fast Drop مصر.\n"
            f"المدير سأل: \"{question}\"\n"
            f"البيانات ({len(df)} صف):\n"
            f"{data_md}\n\n"
            "اكتب تحليل تجاري مختصر (3 جمل بالعربي المصري المهني).\n"
            "استخدم الأرقام الفعلية من البيانات. ابرز أي حاجة غير طبيعية."
        )
    else:
        prompt = (
            f'Admin asked: "{question}"\n'
            f"Data ({len(df)} rows):\n{data_md}\n\n"
            "Write 3-sentence business insight with specific numbers. "
            "Highlight anomalies or actionable recommendations."
        )

    try:
        return call_gemini_with_fallback(prompt, temperature=0.3,
                                         preferred_model="gemini-2.5-flash")
    except Exception:
        return call_groq_with_fallback(
            [{"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=300,
        )


# ═══════════════════════════════════════════════
# Main Analytics Handler
# ═══════════════════════════════════════════════
async def handle_analytics_query(
    question: str,
    db_session,
    engine=None,
    response_lang: str = "ar",
) -> dict:
    """
    Full analytics pipeline:
    1. Get schema
    2. Generate SQL from question
    3. Execute safely
    4. Generate insight
    """
    try:
        # Get schema (Async safe)
        schema = await get_schema_text(engine)

        # Generate SQL
        sql = question_to_sql(question, schema)
        logger.info(f"[Analytics] Generated SQL: {sql}")

        # Execute
        df = await execute_sql(sql, db_session)

        # Generate insight
        insight = generate_insight(question, df, response_lang)

        return {
            "question": question,
            "sql_generated": sql,
            "insight": insight,
            "row_count": len(df),
            "data": df.head(50).to_dict(orient="records"),
            "status": "success",
        }

    except ValueError as e:
        return {
            "question": question,
            "error": str(e),
            "status": "blocked",
        }
    except Exception as e:
        logger.error(f"[Analytics] Error: {e}")
        return {
            "question": question,
            "error": str(e),
            "status": "error",
        }
