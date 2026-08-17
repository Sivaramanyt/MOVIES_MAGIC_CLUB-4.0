from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Movie(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tmdb_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    original_title: Mapped[str | None] = mapped_column(String(500))
    release_date: Mapped[str | None] = mapped_column(String(20))
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    overview: Mapped[str | None] = mapped_column(Text)
    poster_url: Mapped[str | None] = mapped_column(Text)
    backdrop_url: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[float | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    aliases: Mapped[list["MovieAlias"]] = relationship(back_populates="movie", cascade="all, delete-orphan")
    files: Mapped[list["MovieFile"]] = relationship(back_populates="movie")


class MovieAlias(Base):
    __tablename__ = "movie_aliases"
    __table_args__ = (Index("ix_movie_aliases_alias", "alias"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    alias: Mapped[str] = mapped_column(String(500), nullable=False)

    movie: Mapped[Movie] = relationship(back_populates="aliases")


class MovieFile(Base):
    __tablename__ = "movie_files"
    __table_args__ = (
        UniqueConstraint("channel_id", "message_id", name="uq_movie_files_channel_message"),
        Index("ix_movie_files_movie_language_quality", "movie_id", "language", "quality"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movie_id: Mapped[int | None] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), nullable=True, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_file_id: Mapped[str] = mapped_column(String(500), nullable=False)
    file_unique_id: Mapped[str | None] = mapped_column(String(500), index=True)
    filename: Mapped[str] = mapped_column(String(1000), nullable=False)
    parsed_title: Mapped[str | None] = mapped_column(String(500), index=True)
    parsed_year: Mapped[int | None] = mapped_column(Integer, index=True)
    language: Mapped[str | None] = mapped_column(String(100), index=True)
    quality: Mapped[str | None] = mapped_column(String(50), index=True)
    source: Mapped[str | None] = mapped_column(String(50), index=True)
    codec: Mapped[str | None] = mapped_column(String(50))
    audio: Mapped[str | None] = mapped_column(String(50))
    extension: Mapped[str | None] = mapped_column(String(20))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    mime_type: Mapped[str | None] = mapped_column(String(200))
    indexed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    movie: Mapped[Movie | None] = relationship(back_populates="files")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    value: Mapped[str | None] = mapped_column(Text)
