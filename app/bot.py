import logging
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
from app.database.repositories.movie_repository import MovieRepository
from app.database.session import SessionLocal
from app.parser.filename_parser import parse_filename
from app.tmdb import TMDBClient

router = Router()
settings = get_settings()
logger = logging.getLogger(__name__)


def is_admin(message: Message) -> bool:
    configured_ids = getattr(settings, "admin_user_ids", "") or os.getenv("ADMIN_USER_IDS", "")
    admin_ids = {int(value.strip()) for value in configured_ids.split(",") if value.strip().isdigit()}
    return message.from_user is not None and message.from_user.id in admin_ids


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    await message.answer("🎬 <b>MOVIES MAGIC CLUB</b>\n\n✅ Telegram connection is working.\nPhase 1 foundation is online.")


@router.message(Command("repo_test"))
async def repo_test_handler(message: Message) -> None:
    if not is_admin(message):
        await message.answer("⛔ You are not authorized to run this test.")
        return
    await message.answer("🧪 Running Movie Repository test…")
    session: AsyncSession = SessionLocal()
    try:
        result = await run_movie_repository_smoke_test(session)
        await message.answer("🧪 <b>Movie Repository Test</b>\n\nDatabase: ✅\nCreate: " + ("✅" if result["created"] else "❌") + "\nRead: " + ("✅" if result["read_back"] else "❌") + "\nCleanup: " + ("✅" if result["cleaned_up"] else "❌") + "\n\nNo test data was kept.")
    except Exception:
        logger.exception("Movie repository test failed")
        await message.answer("❌ Repository test failed. Check Koyeb logs.")
    finally:
        await session.close()


@router.message(Command("file_test"))
async def file_test_handler(message: Message) -> None:
    if not is_admin(message):
        await message.answer("⛔ You are not authorized to run this test.")
        return
    await message.answer("🧪 Running File Intake database test…")
    session: AsyncSession = SessionLocal()
    try:
        result = await run_file_intake_smoke_test(session)
        await message.answer("🧪 <b>File Intake Test</b>\n\nDatabase: ✅\nCreate: " + ("✅" if result["created"] else "❌") + "\nRead: " + ("✅" if result["read_back"] else "❌") + "\nCleanup: " + ("✅" if result["cleaned_up"] else "❌") + "\n\nNo test data was kept.")
    except Exception:
        logger.exception("File intake test failed")
        await message.answer("❌ File Intake test failed. Check Koyeb logs.")
    finally:
        await session.close()


@router.message(Command("parse_test"))
async def parse_test_handler(message: Message) -> None:
    if not is_admin(message):
        await message.answer("⛔ You are not authorized to run this test.")
        return
    samples = [
        "Leo.2023.Tamil.1080p.WEB-DL.x264.AAC.mkv",
        "Leo.2008.1080p.BluRay.x264.mkv",
        "Pushpa 2 The Rule (2024) Telugu 2160p WEB-DL HEVC DDP.mkv",
        "Interstellar.2014.English.1080p.BluRay.x264.DTS.mkv",
        "Jailer.2023.Tamil.720p.WEBRip.x265.AAC.mp4",
    ]
    passed = 0
    lines = ["🧪 <b>Filename Parser Test</b>", ""]
    for index, filename in enumerate(samples, 1):
        parsed = parse_filename(filename)
        ok = bool(parsed.title and parsed.year is not None)
        passed += int(ok)
        lines.extend([f"<b>{index}. {filename}</b>", f"Title: {parsed.title or 'Unknown'}", f"Year: {parsed.year or 'Unknown'}", f"Language: {parsed.language or 'Unknown'}", f"Quality: {parsed.quality or 'Unknown'}", f"Source: {parsed.source or 'Unknown'}", f"Codec: {parsed.codec or 'Unknown'}", f"Audio: {parsed.audio or 'Unknown'}", f"Extension: {parsed.extension or 'Unknown'}", f"Result: {'✅' if ok else '❌'}", ""])
    lines.append(f"Parser tests: {passed}/{len(samples)} {'✅' if passed == len(samples) else '⚠️'}")
    lines.append("\nTMDB matching: ⏳ Automatic on incoming files")
    lines.append("Movie grouping: ⏳ Later")
    await message.answer("\n".join(lines))


@router.message(Command("tmdb_test"))
async def tmdb_test_handler(message: Message) -> None:
    if not is_admin(message):
        await message.answer("⛔ You are not authorized to run this test.")
        return

    argument = (message.text or "").partition(" ")[2].strip()
    if not argument:
        await message.answer("🧪 <b>TMDB Test</b>\n\nUsage:\n<code>/tmdb_test Leo 2023</code>\n<code>/tmdb_test Interstellar 2014</code>")
        return

    parts = argument.rsplit(" ", 1)
    title = argument
    year = None
    if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 4:
        title = parts[0]
        year = int(parts[1])

    await message.answer(f"🔎 Searching TMDB for <b>{title}</b>{f' ({year})' if year else ''}…")
    try:
        client = TMDBClient()
        best, candidates = await client.match_movie(title, year)
        if not candidates:
            await message.answer("❌ No TMDB movie candidates found.")
            return

        lines = ["🎬 <b>TMDB Match Test</b>", ""]
        if best:
            lines.extend(["✅ <b>Automatic match:</b>", f"Title: {best.title}", f"Year: {best.year or 'Unknown'}", f"TMDB ID: <code>{best.tmdb_id}</code>", f"Score: {best.score:.2f}", ""])
        else:
            lines.extend(["⚠️ <b>No automatic match</b>", "The result is ambiguous or confidence is too low.", ""])

        lines.append("<b>Top candidates:</b>")
        for index, candidate in enumerate(candidates[:3], 1):
            lines.append(f"{index}. {candidate.title} ({candidate.year or '?'}) — {candidate.score:.2f} — ID {candidate.tmdb_id}")
        lines.append("\nDatabase write: ⏳ Not performed")
        lines.append("Movie grouping: ⏳ Not performed")
        await message.answer("\n".join(lines))
    except Exception:
        logger.exception("TMDB test failed")
        await message.answer("❌ <b>TMDB test failed</b>\n\nCheck Koyeb logs.")


@router.message(Command("match_test"))
async def match_test_handler(message: Message) -> None:
    """Mobile-friendly end-to-end parser + TMDB match test without database writes."""
    if not is_admin(message):
        await message.answer("⛔ You are not authorized to run this test.")
        return
    filename = (message.text or "").partition(" ")[2].strip()
    if not filename:
        await message.answer("🧪 <b>Match Test</b>\n\nUsage:\n<code>/match_test Leo.2023.Tamil.1080p.WEB-DL.mkv</code>")
        return
    parsed = parse_filename(filename)
    if not parsed.title:
        await message.answer("⚠️ Could not extract a movie title from this filename.")
        return
    await message.answer(f"🔎 Matching <b>{parsed.title}</b>{f' ({parsed.year})' if parsed.year else ''} with TMDB…")
    try:
        best, candidates = await TMDBClient().match_movie(parsed.title, parsed.year)
        lines = ["🧪 <b>Match Test</b>", "", f"Parsed title: {parsed.title}", f"Parsed year: {parsed.year or 'Unknown'}", ""]
        if best:
            lines.extend(["✅ <b>HIGH-CONFIDENCE MATCH</b>", f"TMDB: {best.title} ({best.year or '?'})", f"TMDB ID: <code>{best.tmdb_id}</code>", f"Score: {best.score:.2f}", "Database write: ⏳ Test only"])
        elif candidates:
            top = candidates[0]
            lines.extend(["⚠️ <b>NO AUTOMATIC MATCH</b>", f"Best candidate: {top.title} ({top.year or '?'})", f"Score: {top.score:.2f}", "Reason: confidence/margin below automatic threshold.", "Database write: ⏳ Test only"])
        else:
            lines.append("❌ No TMDB candidates found.")
        await message.answer("\n".join(lines))
    except Exception:
        logger.exception("Match test failed")
        await message.answer("❌ Match test failed. Check Koyeb logs.")


async def _handle_telegram_file(message: Message) -> None:
    """Persist a Telegram file, then attach it to a high-confidence TMDB movie."""
    session: AsyncSession = SessionLocal()
    try:
        if message.document is not None:
            file = message.document
            filename = file.file_name or f"document_{message.message_id}"
            file_id, unique_id = file.file_id, file.file_unique_id
            file_size, mime_type = file.file_size, file.mime_type
        elif message.video is not None:
            file = message.video
            filename = f"video_{message.message_id}.mp4"
            file_id, unique_id = file.file_id, file.file_unique_id
            file_size, mime_type = file.file_size, file.mime_type or "video/mp4"
        else:
            return

        parsed = parse_filename(filename)
        file_repository = MovieFileRepository(session)
        row, created = await file_repository.create_or_get(
            channel_id=message.chat.id,
            message_id=message.message_id,
            telegram_file_id=file_id,
            file_unique_id=unique_id,
            filename=filename,
            file_size=file_size,
            mime_type=mime_type,
            parsed=parsed,
        )
        if not created:
            await session.rollback()
            await message.answer("📥 File already indexed. No duplicate record created.")
            return

        match_status = "⚠️ Unmatched"
        matched_title = None
        if parsed.title:
            try:
                best, _ = await TMDBClient().match_movie(parsed.title, parsed.year)
                if best:
                    movie_repository = MovieRepository(session)
                    movie, _ = await movie_repository.get_or_create_by_tmdb(
                        tmdb_id=best.tmdb_id,
                        title=best.title,
                        original_title=best.original_title,
                        release_date=best.release_date,
                        year=best.year,
                        overview=best.overview,
                        poster_url=best.poster_url,
                        backdrop_url=best.backdrop_url,
                        rating=best.rating,
                    )
                    await file_repository.attach_movie(row, movie)
                    await movie_repository.add_alias(movie, parsed.title)
                    matched_title = movie.title
                    match_status = f"✅ Matched: {movie.title} ({movie.year or '?'})"
            except Exception:
                logger.exception("Automatic TMDB matching failed for file %s", filename)
                match_status = "⚠️ Stored, TMDB matching failed"

        await session.commit()
        await message.answer(
            "📥 <b>File indexed</b>\n\n"
            f"Name: <code>{filename}</code>\n"
            f"Title: {parsed.title or 'Unknown'}\n"
            f"Year: {parsed.year or 'Unknown'}\n"
            f"Language: {parsed.language or 'Unknown'}\n"
            f"Quality: {parsed.quality or 'Unknown'}\n"
            f"Source: {parsed.source or 'Unknown'}\n\n"
            "Database: ✅\n"
            f"TMDB: {match_status}\n"
            "Movie grouping: ⏳ Later"
        )
    except Exception:
        await session.rollback()
        logger.exception("Telegram file intake failed")
        await message.answer("⚠️ File received, but database storage failed. Check Koyeb logs.")
    finally:
        await session.close()


@router.message(F.document | F.video)
async def telegram_file_message_handler(message: Message) -> None:
    await _handle_telegram_file(message)


@router.channel_post(F.document | F.video)
async def telegram_file_channel_post_handler(message: Message) -> None:
    await _handle_telegram_file(message)


@router.message()
async def message_handler(message: Message) -> None:
    await message.answer("👋 Hello! The bot is receiving Telegram messages correctly.")


def create_bot(token: str) -> Bot:
    return Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher
