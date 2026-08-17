import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.movie_file_repository import MovieFileRepository


async def run_file_intake_smoke_test(session: AsyncSession) -> dict:
    """Create, read, and roll back one synthetic Telegram file record."""
    marker = uuid.uuid4().hex
    channel_id = -1000000000000 - int(marker[:6], 16)
    message_id = int(marker[6:14], 16)
    file_id = f"__MMC_FILE_TEST__{marker}"
    filename = f"__MMC_FILE_TEST__{marker}.mkv"

    repository = MovieFileRepository(session)
    try:
        row, created = await repository.create_or_get(
            channel_id=channel_id,
            message_id=message_id,
            telegram_file_id=file_id,
            file_unique_id=f"unique-{marker}",
            filename=filename,
            file_size=123456,
            mime_type="video/x-matroska",
        )
        if not created:
            raise RuntimeError("file test record unexpectedly already exists")

        read_row = await repository.get_by_channel_message(channel_id, message_id)
        if read_row is None or read_row.id != row.id:
            raise RuntimeError("file repository read-back verification failed")

        await session.rollback()
        return {"success": True, "created": True, "read_back": True, "cleaned_up": True}
    except Exception:
        await session.rollback()
        raise
