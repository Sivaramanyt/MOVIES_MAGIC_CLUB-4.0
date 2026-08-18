from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedFilename:
    title: str
    year: int | None
    language: str | None
    quality: str | None
    source: str | None
    codec: str | None
    audio: str | None
    extension: str | None


QUALITY_RE = re.compile(r"(?i)(2160p|4k|1440p|1080p|720p|576p|480p)")
YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")

LANGUAGES = {
    "tamil": "Tamil", "tam": "Tamil",
    "telugu": "Telugu", "tel": "Telugu",
    "malayalam": "Malayalam", "mal": "Malayalam",
    "kannada": "Kannada", "kan": "Kannada",
    "hindi": "Hindi", "hin": "Hindi",
    "english": "English", "eng": "English",
    "bengali": "Bengali", "ben": "Bengali",
    "marathi": "Marathi", "mar": "Marathi",
    "punjabi": "Punjabi", "pun": "Punjabi",
}

SOURCES = ["WEB-DL", "WEBRip", "WEB-RIP", "BluRay", "BDRip", "BRRip", "HDRip", "HDTV", "DVDRip", "CAM", "HDCAM", "TS"]
CODECS = ["x265", "x264", "H.265", "H265", "H.264", "H264", "AV1", "HEVC", "AVC"]
AUDIOS = ["AAC", "AC3", "DDP", "DD+", "EAC3", "DTS", "MP3", "TRUEHD", "ATMOS"]


def _find_case_insensitive(text: str, values: list[str]) -> str | None:
    for value in values:
        if re.search(rf"(?i)(?<![A-Za-z0-9]){re.escape(value)}(?![A-Za-z0-9])", text):
            return value
    return None


def _clean_title(text: str) -> str:
    # Remove common leading/trailing release punctuation and bracket residue.
    text = re.sub(r"[\[\](){}]", " ", text)
    text = re.sub(r"[._]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -_.")
    return text.strip()


def _strip_leading_metadata(text: str) -> str:
    """Remove release metadata that appears before the movie title."""
    pattern = re.compile(
        r"(?i)^\s*(?:[\[({]\s*)?"
        r"(?:2160p|4k|1440p|1080p|720p|576p|480p|"
        r"tamil|tam|telugu|tel|malayalam|mal|kannada|kan|"
        r"hindi|hin|english|eng|bengali|ben|marathi|mar|punjabi|pun|"
        r"web-dl|web[- ]?rip|bluray|bdrip|brrip|hdrip|hdtv|dvdrip|cam|hdtc|ts|"
        r"x264|x265|h\.264|h264|h\.265|h265|hevc|av1|aac|ac3|ddp|dd\+|eac3|dts|mp3|truehd|atmos"
        r")\b\s*(?:[\]})]\s*)?[-_. ]*"
    )
    previous = None
    while previous != text:
        previous = text
        text = pattern.sub("", text).strip()
    return text


def parse_filename(filename: str) -> ParsedFilename:
    """Parse common movie filename metadata without identifying the actual movie."""
    extension = Path(filename).suffix.lower() or None
    stem = Path(filename).stem
    year_match = YEAR_RE.search(stem)
    year = int(year_match.group(1)) if year_match else None

    quality_match = QUALITY_RE.search(stem)
    quality = quality_match.group(1).upper() if quality_match else None
    if quality == "4K":
        quality = "2160p"

    language = None
    lower = stem.lower()
    for key, display in LANGUAGES.items():
        if re.search(rf"(?<![a-z]){re.escape(key)}(?![a-z])", lower):
            language = display
            break

    source = _find_case_insensitive(stem, SOURCES)
    codec = _find_case_insensitive(stem, CODECS)
    audio = _find_case_insensitive(stem, AUDIOS)

    # First remove leading release tags such as [Tamil] [1080p] before finding
    # the actual title. This fixes a common source of empty/garbled titles.
    title_source = _strip_leading_metadata(stem)
    title_source = re.sub(r"^\s*[\[({]\s*", "", title_source)

    year_match_title = YEAR_RE.search(title_source)
    quality_match_title = QUALITY_RE.search(title_source)
    cut_points = [m.start() for m in (year_match_title, quality_match_title) if m]

    for value in [language, source, codec, audio]:
        if value:
            match = re.search(
                rf"(?i)(?<![A-Za-z0-9]){re.escape(value)}(?![A-Za-z0-9])",
                title_source,
            )
            if match:
                cut_points.append(match.start())

    title_end = min(cut_points) if cut_points else len(title_source)
    title = _clean_title(title_source[:title_end])

    # Some release names put metadata in a bracket immediately after the title.
    # Remove that trailing metadata without damaging ordinary movie titles.
    title = re.sub(
        r"\s+[\[({]\s*(?:19|20)\d{2}|\s+[\[({]\s*(?:2160p|4k|1440p|1080p|720p|576p|480p)\b.*$",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()

    return ParsedFilename(
        title=title,
        year=year,
        language=language,
        quality=quality,
        source=source,
        codec=codec,
        audio=audio,
        extension=extension,
    )
