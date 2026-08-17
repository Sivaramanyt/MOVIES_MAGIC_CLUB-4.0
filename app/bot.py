from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message
from aiogram.filters import Command, CommandStart
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.repository_diagnostics import run_movie_repository_smoke_test
from app.database.session import SessionLocal

router = Router()
settings = get_settings()


def is_admin(message: Message) -> bool:
    """Allow only the configured Telegram admin user to run diagnostics."""
    admin_ids = {
        int(value.strip())
        for value in settings.admin_user_ids.split(",")
        if value.strip().isdigit()
    }
    return message.from_user is not None and message.from_user.id in admin_ids


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    await message.answer(
        "🎬 <b>MOVIES MAGIC CLUB</b>\n\n"
        "✅ Telegram connection is working.\n"
        "Phase 1 foundation is online."
    )


@router.message(Command("repo_test"))
async def repo_test_handler(message: Message) -> None:
    if not is_admin(message):
        await message.answer("⛔ You are not authorized to run this test.")
        return

    await message.answer("🧪 Running Movie Repository test…")
    session: AsyncSession = SessionLocal()
    try:
        result = await run_movie_repository_smoke_test(session)
        await message.answer(
            "🧪 <b>Movie Repository Test</b>\n\n"
            f"Database: ✅\n"
            f"Create: {'✅' if result['created'] else '❌'}\n"
            f"Read: {'✅' if result['read_back'] else '❌'}\n"
            f"Cleanup: {'✅' if result['cleaned_up'] else '❌'}\n\n"
            "No test data was kept."
        )
    except Exception:
        await message.answer("❌ Repository test failed. Check Koyeb logs.")
    finally:
        await session.close()


@router.message()
async def message_handler(message: Message) -> None:
    await message.answer("👋 Hello! The bot is receiving Telegram messages correctly.")


def create_bot(token: str) -> Bot:
    return Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher
