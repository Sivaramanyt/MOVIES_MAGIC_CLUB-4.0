import os

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message
from aiogram.filters import Command, CommandStart
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.file_intake_diagnostics import run_file_intake_smoke_test
from app.database.repository_diagnostics import run_movie_repository_smoke_test
from app.database.repositories.movie_file_repository import MovieFileRepository
from app.database.session import SessionLocal

router = Router()
settings = get_settings()


def is_admin(message: Message) -> bool:
    """Allow only configured Telegram admin user IDs to run diagnostics."""
    configured_ids = getattr(settings, "admin_user_ids", "") or os.getenv("ADMIN_USER_IDS", "")
    admin_ids = {
        int(value.strip())
        for value in configured_ids.split(",")
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


@router.message(Command("file_test"))
async def file_test_handler(message: Message) -> None:
    """Mobile-friendly admin smoke test for MovieFile persistence."""
    if not is_admin(message):
        await message.answer("⛔ You are not authorized to run this test.")
        return

    await message.answer("🧪 Running File Intake database test…")
    session: AsyncSession = SessionLocal()
    try:
        result = await run_file_intake_smoke_test(session)
        await message.answer(
            "🧪 <b>File Intake Test</b>\n\n"
            f"Database: ✅\n"
            f"Create: {'✅' if result['created'] else '❌'}\n"
            f"Read: {'✅' if result['read_back'] else '❌'}\n"
            f"Cleanup: {'✅' if result['cleaned_up'] else '❌'}\n\n"
            "No test data was kept."
        )
    except Exception:
        await message.answer("❌ File Intake test failed. Check Koyeb logs.")
    finally:
        await session.close()


@router.message(F.document | F.video)
async def telegram_file_handler(message: Message) -> None:
    """Persist raw Telegram document/video metadata without grouping or TMDB."""
    session: AsyncSession = SessionLocal()
    try:
        if message.document is not None:
            file = message.document
            filename = file.file_name or f"document_{message.message_id}"
            file_id = file.file_id
            unique_id = file.file_unique_id
            file_size = file.file_size
            mime_type = file.mime_type
        else:
            file = message.video
            filename = f"video_{message.message_id}.mp4"
            file_id = file.file_id
            unique_id = file.file_unique_id
            file_size = file.file_size
            mime_type = file.mime_type or "video/mp4"

        repository = MovieFileRepository(session)
        row, created = await repository.create_or_get(
            channel_id=message.chat.id,
            message_id=message.message_id,
            telegram_file_id=file_id,
            file_unique_id=unique_id,
            filename=filename,
            file_size=file_size,
            mime_type=mime_type,
        )
        if created:
            await session.commit()
            await message.answer(
                "📥 <b>File received</b>\n\n"
                f"Name: <code>{filename}</code>\n"
                "Database: ✅\n"
                "Status: Stored\n"
                "Movie grouping: ⏳ Later"
            )
        else:
            await session.rollback()
            await message.answer("📥 File already indexed. No duplicate record created.")
    except Exception:
        await session.rollback()
        # Do not let a file-processing failure break Telegram webhook delivery.
        await message.answer("⚠️ File received, but database storage failed. Check Koyeb logs.")
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
