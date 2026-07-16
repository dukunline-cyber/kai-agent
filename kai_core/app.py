"""Split from telegram_agent monolith — behavior preserved."""
from __future__ import annotations

from kai_core.config import *  # noqa: F401,F403

from kai_handlers.all_handlers import *  # noqa: F401,F403

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("memory", memory_cmd))
    app.add_handler(CommandHandler("remember", remember_cmd))
    app.add_handler(CommandHandler("forget", forget_cmd))
    app.add_handler(CommandHandler("model", model_cmd))
    app.add_handler(CommandHandler("models", models_cmd))
    app.add_handler(CommandHandler("setmodel", setmodel_cmd))
    app.add_handler(CommandHandler("aws", aws_cmd))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(CommandHandler("remote", remote_cmd))
    app.add_handler(CommandHandler("setremote", setremote))
    app.add_handler(CommandHandler("setremote_key", setremote_key))
    app.add_handler(CommandHandler("remote_status", remote_status))
    app.add_handler(CommandHandler("oracle_setup", oracle_setup))
    app.add_handler(CommandHandler("oracle_config", oracle_config_cmd))
    app.add_handler(CommandHandler("oracle_key", oracle_key_cmd))
    app.add_handler(CommandHandler("oracle_war", oracle_war_cmd))
    app.add_handler(CommandHandler("oracle_stop", oracle_stop_cmd))
    app.add_handler(CommandHandler("oracle_status", oracle_status_cmd))
    app.add_handler(CommandHandler("oracle_reset", oracle_reset_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CommandHandler("soul", soul_cmd))
    app.add_handler(CommandHandler("soul_reload", soul_reload_cmd))
    app.add_handler(CommandHandler("creds", creds_cmd))
    app.add_handler(CommandHandler("tts", tts_cmd))
    app.add_handler(CommandHandler("reminders", reminders_cmd))
    app.add_handler(CommandHandler("delreminder", del_reminder_cmd))
    app.add_handler(CommandHandler("dbstats", db_stats_cmd))
    app.add_handler(CommandHandler("retry", retry_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE, handle_video))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    print(f"{AGENT_NAME} aktif. Model: {DEFAULT_MODEL}")

    # Migrate JSON data to SQLite on first run
    try:
        migrate_json_to_db()
    except Exception as e:
        logging.warning(f"Migration skipped: {e}")

    app.add_error_handler(error_handler)

    # Start reminder checker as post_init
    async def heartbeat_logger():
        """Log periodic heartbeat so self_heal knows we are alive."""
        while True:
            await asyncio.sleep(120)
            logging.info("heartbeat OK")

    async def post_init(application):
        asyncio.create_task(reminder_check_loop(application))
        asyncio.create_task(heartbeat_logger())
        asyncio.create_task(reflect_loop())

    app.post_init = post_init
    app.run_polling()



