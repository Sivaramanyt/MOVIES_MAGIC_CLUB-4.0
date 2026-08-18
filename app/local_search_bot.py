from collections import Counter
import os

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.local_grouping import group_unmatched_files
from app.database.repositories.movie_repository import MovieRepository
from app.database.session import SessionLocal

router = Router()
settings = get_settings()


def _is_admin(message: Message) -> bool:
    configured = getattr(settings, "admin_user_ids", "") or os.getenv("ADMIN_USER_IDS", "")
    ids = {int(v.strip()) for v in configured.split(",") if v.strip().isdigit()}
    return message.from_user is not None and message.from_user.id in ids


@router.message(Command("local_group"))
async def local_group_handler(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("⛔ You are not authorized to run local grouping.")
        return

    argument = (message.text or "").partition(" ")[2].strip()
    limit = 500
    if argument:
        if not argument.isdigit() or int(argument) <= 0:
            await message.answer("Usage: <code>/local_group 500</code>")
            return
        limit = min(int(argument), 5000)

    await message.answer(
        "🗂 <b>Database-first grouping started</b>\n\n"
        f"Batch size: <b>{limit}</b>\n"
        "TMDB is not required.\n"
        "Grouping key: normalized title + year.\n\n"
        "⏳ Please wait…"
    )
    session: AsyncSession = SessionLocal()
    try:
        result = await group_unmatched_files(session, limit)
        await message.answer(
            "🗂 <b>Database-first grouping complete</b>\n\n"
            f"Processed: <b>{result.processed}</b>\n"
            f"Grouped: <b>{result.grouped}</b>\n"
            f"New local groups: <b>{result.new_groups}</b>\n"
            f"Existing groups reused: <b>{result.existing_groups}</b>\n"
            f"Skipped: <b>{result.skipped}</b>\n\n"
            "✅ No TMDB match was required.\n"
            "✅ Channel + message identity was unchanged.\n"
            "✅ Existing TMDB groups were not modified."
        )
    except Exception:
        await session.rollback()
        await message.answer("❌ Local grouping failed. Existing database records were not deleted.")
    finally:
        await session.close()


@router.message(Command("search"))
async def database_search_handler(message: Message) -> None:
    query = (message.text or "").partition(" ")[2].strip()
    if not query:
        await message.answer("🔎 <b>Movie Search</b>\n\nUsage:\n<code>/search Leo</code>\n<code>/search Transformers</code>")
        return

    session: AsyncSession = SessionLocal()
    try:
        repository = MovieRepository(session)
        movies = await repository.find_by_title(query)
        if not movies:
            await message.answer(f"🔎 No movie found for <b>{query}</b>.\n\nTMDB is not required for database search.")
            return

        buttons: list[list[InlineKeyboardButton]] = []
        lines = ["🔎 <b>Movie Search</b>", "", f"Results for: <b>{query}</b>", ""]
        for index, movie in enumerate(movies[:20], 1):
            languages = sorted({f.language for f in movie.files if f.language})
            language_text = ", ".join(languages[:3]) if languages else "Language unknown"
            tmdb_text = "TMDB ✅" if movie.tmdb_id is not None else "Local DB"
            lines.append(f"<b>{index}. {movie.title} ({movie.year or '?'})</b>")
            lines.append(f"   {language_text} · {len(movie.files)} file(s) · {tmdb_text}")
            buttons.append([InlineKeyboardButton(text=f"🎬 {movie.title} ({movie.year or '?'})", callback_data=f"dbmovie:{movie.id}")])

        if len(movies) > 20:
            lines.append(f"\n…and {len(movies) - 20} more results")
        await message.answer("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    finally:
        await session.close()


@router.callback_query(F.data.startswith("dbmovie:"))
async def database_movie_handler(callback: CallbackQuery) -> None:
    try:
        movie_id = int((callback.data or "dbmovie:0").split(":", 1)[1])
    except ValueError:
        await callback.answer("❌ Invalid movie.", show_alert=True)
        return

    session: AsyncSession = SessionLocal()
    try:
        repository = MovieRepository(session)
        movie = await repository.get_by_id(movie_id)
        if movie is None:
            await callback.answer("❌ Movie group not found.", show_alert=True)
            return

        lines = [
            "🎬 <b>Movie</b>",
            "",
            f"<b>{movie.title}</b> ({movie.year or '?'})",
            f"Identity: {'TMDB ' + str(movie.tmdb_id) if movie.tmdb_id else 'Database-first local group'}",
            "",
        ]
        grouped: dict[str, Counter] = {}
        for file in movie.files:
            language = file.language or "Unknown"
            quality = file.quality or "Unknown"
            grouped.setdefault(language, Counter())[quality] += 1
        for language, qualities in sorted(grouped.items()):
            lines.append(f"🌐 <b>{language}</b>")
            lines.append("   " + " · ".join(f"{q}: {n}" for q, n in sorted(qualities.items())))
        lines.append(f"\n📁 Total files: <b>{len(movie.files)}</b>")
        if movie.tmdb_id is not None:
            lines.append(f"🎯 TMDB ID: <code>{movie.tmdb_id}</code>")
        else:
            lines.append("ℹ️ TMDB metadata is optional for this group.")
        await callback.message.answer("\n".join(lines))
        await callback.answer()
    finally:
        await session.close()
