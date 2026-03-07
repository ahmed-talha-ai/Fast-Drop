# tg_bot/bot.py
# ═══════════════════════════════════════════════════════════════════
# Fast Drop Telegram Bot — Egyptian Arabic First
# Commands, inline keyboards, deep-link order tracking,
# rate-limit-aware notifications
# ═══════════════════════════════════════════════════════════════════
import os
import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters,
)

logger = logging.getLogger("fastdrop.telegram")


# ═══════════════════════════════════════════════
# Bot Setup
# ═══════════════════════════════════════════════
def create_bot_app() -> Application:
    """Build and configure the Telegram bot application."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")

    app = Application.builder().token(token).build()

    # Register handlers
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("track", handle_track))
    app.add_handler(CommandHandler("zones", handle_zones))
    app.add_handler(CommandHandler("fees", handle_fees))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_message
    ))

    return app


# ═══════════════════════════════════════════════
# Arabic Reply Keyboard
# ═══════════════════════════════════════════════
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["📦 تتبع الأوردر", "💬 محادثة"],
        ["📍 مناطق التوصيل", "💰 رسوم التوصيل"],
        ["📞 خدمة العملاء", "❓ مساعدة"],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)


# ═══════════════════════════════════════════════
# /start Command
# ═══════════════════════════════════════════════
async def handle_start(update: Update, context) -> None:
    """Welcome message with Arabic keyboard."""
    # Check for deep-link (e.g., /start track_ORD-2026-12345)
    args = context.args
    if args and args[0].startswith("track_"):
        order_id = args[0].replace("track_", "")
        await _show_order_status(update, context, order_id)
        return

    welcome = (
        "🚚 *أهلاً بيك في فاست دروب!*\n\n"
        "أنا البوت بتاعك للتوصيل في مصر 🇪🇬\n"
        "اكتبلي أي حاجة بالعربي أو الإنجليزي وهساعدك.\n\n"
        "🔹 تتبع أوردرك — ابعتلي رقمه\n"
        "🔹 اسأل عن المناطق والرسوم\n"
        "🔹 قدم شكوى أو اتواصل مع الدعم\n\n"
        "_مدعوم بالذكاء الاصطناعي — بفهم عربي ومصري وفرانكو_"
    )
    await update.message.reply_text(
        welcome,
        reply_markup=MAIN_KEYBOARD,
        parse_mode="Markdown",
    )


# ═══════════════════════════════════════════════
# /help Command
# ═══════════════════════════════════════════════
async def handle_help(update: Update, context) -> None:
    """Display available commands in Arabic."""
    help_text = (
        "📋 *الأوامر المتاحة:*\n\n"
        "/start — ابدأ من الأول\n"
        "/track `رقم_الأوردر` — تتبع أوردرك\n"
        "/zones — مناطق التوصيل\n"
        "/fees — رسوم التوصيل\n"
        "/help — الأوامر دي\n\n"
        "أو اكتب أي سؤال بالعربي وأنا هساعدك! 🤖"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


# ═══════════════════════════════════════════════
# /track Command
# ═══════════════════════════════════════════════
async def handle_track(update: Update, context) -> None:
    """Track an order by ID."""
    if not context.args:
        await update.message.reply_text(
            "📦 ابعتلي رقم الأوردر كده:\n"
            "/track ORD-2026-12345"
        )
        return

    order_id = context.args[0].upper()
    await _show_order_status(update, context, order_id)


async def _show_order_status(update, context, order_id: str) -> None:
    """Fetch and display order status with inline actions."""
    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    from core.arabic_normalizer import arabic_status

    # Query DB
    try:
        from database import AsyncSessionLocal
        from models import Order
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Order).where(Order.id == order_id))
            order = result.scalar_one_or_none()

            if not order:
                await update.message.reply_text(
                    f"❌ مش لاقي أوردر بالرقم: {order_id}\n"
                    f"تأكد من الرقم وحاول تاني."
                )
                return

            status_ar = arabic_status(
                order.status.value if hasattr(order.status, "value") else str(order.status)
            )
            status_text = (
                f"📦 *أوردر #{order.id}*\n\n"
                f"📊 الحالة: {status_ar}\n"
                f"📍 العنوان: {order.delivery_address[:50]}\n"
                f"💰 رسوم التوصيل: {order.delivery_fee or 'غير محدد'} جنيه\n"
            )

            if order.eta:
                status_text += f"⏰ الموعد المتوقع: {order.eta}\n"

            # Inline keyboard for actions
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔄 تحديث", callback_data=f"refresh_{order.id}"),
                    InlineKeyboardButton("📞 اتصل بالدعم", callback_data="support"),
                ],
            ])

            await update.message.reply_text(
                status_text, parse_mode="Markdown", reply_markup=keyboard
            )

    except Exception as e:
        logger.error(f"Order tracking error: {e}")
        await update.message.reply_text(
            "⚠️ حصلت مشكلة في جلب بيانات الأوردر. حاول تاني كمان شوية."
        )


# ═══════════════════════════════════════════════
# /zones Command
# ═══════════════════════════════════════════════
async def handle_zones(update: Update, context) -> None:
    """List all delivery zones."""
    from core.zone_manager import CAIRO_ZONES

    zone_list = "📍 *مناطق التوصيل في القاهرة والجيزة:*\n\n"
    for z in CAIRO_ZONES:
        zone_list += f"▪️ {z['name_ar']} ({z['name_en']}) — {z['base_fee']} جنيه\n"

    zone_list += "\n_الأسعار بتبدأ من الرسم الأساسي + 3 جنيه/كم بعد أول 3 كم_"
    await update.message.reply_text(zone_list, parse_mode="Markdown")


# ═══════════════════════════════════════════════
# /fees Command
# ═══════════════════════════════════════════════
async def handle_fees(update: Update, context) -> None:
    """Explain delivery fee structure."""
    fees_text = (
        "💰 *رسوم التوصيل:*\n\n"
        "▪️ المناطق القريبة (وسط البلد، شبرا): من 25 جنيه\n"
        "▪️ المناطق المتوسطة (مدينة نصر، المعادي): من 30 جنيه\n"
        "▪️ المناطق البعيدة (التجمع، الرحاب): من 35-40 جنيه\n"
        "▪️ مدن جديدة (6 أكتوبر، العاشر): من 45-55 جنيه\n\n"
        "📏 رسوم إضافية: 3 جنيه لكل كم بعد أول 3 كم\n"
        "💳 عمولة الدفع عند الاستلام: 2%\n"
        "🔄 رسوم الإرجاع: 20 جنيه"
    )
    await update.message.reply_text(fees_text, parse_mode="Markdown")


# ═══════════════════════════════════════════════
# Callback (Inline button presses)
# ═══════════════════════════════════════════════
async def handle_callback(update: Update, context) -> None:
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("refresh_"):
        order_id = data.replace("refresh_", "")
        await query.edit_message_text("🔄 جاري التحديث...")
        await _show_order_status(update, context, order_id)

    elif data == "support":
        await query.edit_message_text(
            "📞 *خدمة العملاء:*\n\n"
            "📱 اتصل: 19555\n"
            "📧 إيميل: support@fastdrop.eg\n"
            "⏰ من 9 الصبح لـ 10 بالليل",
            parse_mode="Markdown",
        )


# ═══════════════════════════════════════════════
# Free-text Message Handler (AI Pipeline)
# ═══════════════════════════════════════════════
async def handle_message(update: Update, context) -> None:
    """
    Handle free-text messages through the full AI pipeline.
    Supports: Egyptian Arabic, MSA, Arabizi, English, mixed.
    """
    user_text = update.message.text
    chat_id = update.effective_chat.id

    # Handle keyboard button presses
    button_map = {
        "📦 تتبع الأوردر": "ابعتلي رقم الأوردر (مثال: ORD-2026-12345) وهاتبعه.",
        "📍 مناطق التوصيل": None,  # Trigger /zones
        "💰 رسوم التوصيل": None,   # Trigger /fees
        "📞 خدمة العملاء": (
            "📞 خدمة العملاء:\n"
            "📱 اتصل: 19555\n"
            "📧 إيميل: support@fastdrop.eg\n"
            "⏰ من 9 الصبح لـ 10 بالليل"
        ),
        "❓ مساعدة": None,  # Trigger /help
    }

    if user_text in button_map:
        if user_text == "📍 مناطق التوصيل":
            return await handle_zones(update, context)
        elif user_text == "💰 رسوم التوصيل":
            return await handle_fees(update, context)
        elif user_text == "❓ مساعدة":
            return await handle_help(update, context)
        elif button_map[user_text]:
            return await update.message.reply_text(button_map[user_text])

    if user_text == "💬 محادثة":
        return await update.message.reply_text(
            "اكتبلي أي سؤال وهحاول أساعدك! 🤖"
        )

    # Show typing indicator
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # Full AI pipeline (NLP chatbot)
    try:
        from database import AsyncSessionLocal
        from ai.nlp_chatbot import handle_chat_bilingual

        async with AsyncSessionLocal() as db:
            reply = await handle_chat_bilingual(
                raw_user_msg=user_text,
                db_session=db,
                vector_index=context.bot_data.get("vector_index"),
                bm25_retriever=context.bot_data.get("bm25_retriever"),
            )
        await update.message.reply_text(reply)

    except Exception as e:
        logger.error(f"Chat error: {e}")
        await update.message.reply_text(
            "⚠️ حصلت مشكلة مؤقتة. حاول تاني كمان شوية أو كلم الدعم."
        )


# ═══════════════════════════════════════════════
# Notification Sending Helper
# ═══════════════════════════════════════════════
async def send_notification(bot, chat_id: str, message: str):
    """Send a notification to a specific chat (customer or driver)."""
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="HTML",
        )
        logger.info(f"[Telegram] Sent notification to {chat_id}")
    except Exception as e:
        logger.error(f"[Telegram] Failed to send to {chat_id}: {e}")


async def send_bulk_notifications(bot, messages: list[dict]):
    """
    Send batch notifications with rate limiting.
    messages: [{"chat_id": ..., "text": ...}, ...]
    Telegram limit: 30 messages/sec, 20 messages/min to same group
    """
    import asyncio

    for msg in messages:
        try:
            await bot.send_message(
                chat_id=msg["chat_id"],
                text=msg["text"],
                parse_mode="HTML",
            )
            await asyncio.sleep(0.05)  # 20 msg/sec (conservative)
        except Exception as e:
            logger.warning(f"[Telegram Bulk] Failed {msg['chat_id']}: {e}")
