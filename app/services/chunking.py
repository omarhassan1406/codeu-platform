"""Chunking strategies for ingesting lesson Markdown into the vector store.

``CharacterChunker`` (default) is structure aware: it splits Markdown into
headings, paragraphs and fenced code blocks first, packs those blocks into
chunks of at most ``chunk_size`` characters, and only cuts inside a block when
the block alone is too large. Code is cut on line boundaries and every piece is
re-wrapped in its own fence, so a retrieved chunk never contains broken code
formatting. Consecutive chunks share up to ``overlap`` characters of context.

``WordChunker`` reproduces the original flat word windows exactly, for
backwards compatibility with content that was already ingested that way.
"""

from typing import Protocol

from app.core.config import settings

FENCE = "```"


class ChunkingStrategy(Protocol):
    name: str

    def split(self, text: str) -> list[str]: ...


class WordChunker:
    """Legacy strategy: windows of ``chunk_size`` words, ``overlap`` words shared."""

    name = "word"

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> list[str]:
        words = text.split()
        step = self.chunk_size - self.overlap
        return [" ".join(words[i:i + self.chunk_size]) for i in range(0, len(words), step)]


def _merge(pieces: list[str], size: int, overlap: int, sep: str) -> list[str]:
    """Pack pieces into chunks of at most ``size`` chars joined by ``sep``.

    When a chunk is emitted, trailing pieces totalling at most ``overlap`` chars
    are carried into the next chunk as shared context.
    """
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for piece in pieces:
        added = len(piece) + (len(sep) if current else 0)
        if current and length + added > size:
            chunks.append(sep.join(current))
            while current and (length > overlap or length + len(sep) + len(piece) > size):
                removed = current.pop(0)
                length -= len(removed) + (len(sep) if current else 0)
            added = len(piece) + (len(sep) if current else 0)
        current.append(piece)
        length += added
    if current:
        chunks.append(sep.join(current))
    return chunks


_PROSE_SEPARATORS = ("\n", ". ", " ", "")


def _split_prose(text: str, size: int, overlap: int, separators=_PROSE_SEPARATORS) -> list[str]:
    if len(text) <= size:
        return [text]
    sep = next(s for s in separators if s == "" or s in text)
    if sep == "":
        step = max(1, size - overlap)
        return [text[i:i + size] for i in range(0, len(text), step)]
    remaining = separators[separators.index(sep) + 1:]
    pieces: list[str] = []
    for part in text.split(sep):
        if len(part) > size:
            pieces.extend(_split_prose(part, size, overlap, remaining))
        elif part:
            pieces.append(part)
    return _merge(pieces, size, overlap, sep)


def _split_code(block: str, size: int) -> list[str]:
    lines = block.split("\n")
    opening = lines[0]
    body = lines[1:-1] if len(lines) > 1 and lines[-1].strip().startswith(FENCE) else lines[1:]
    budget = max(20, size - len(opening) - len(FENCE) - 2)

    groups: list[list[str]] = []
    current: list[str] = []
    length = 0
    for line in body:
        parts = [line[i:i + budget] for i in range(0, len(line), budget)] or [""]
        for part in parts:
            added = len(part) + (1 if current else 0)
            if current and length + added > budget:
                groups.append(current)
                current, length = [], 0
                added = len(part)
            current.append(part)
            length += added
    if current:
        groups.append(current)
    return [f"{opening}\n" + "\n".join(group) + f"\n{FENCE}" for group in groups]


def _markdown_blocks(text: str) -> list[tuple[str, str]]:
    """Split Markdown into ("code" | "prose", block) pieces in document order."""
    blocks: list[tuple[str, str]] = []
    prose: list[str] = []
    code: list[str] | None = None

    def flush_prose() -> None:
        if prose:
            blocks.append(("prose", "\n".join(prose)))
            prose.clear()

    for line in text.splitlines():
        stripped = line.strip()
        if code is not None:
            code.append(line)
            if stripped.startswith(FENCE):
                blocks.append(("code", "\n".join(code)))
                code = None
            continue
        if stripped.startswith(FENCE):
            flush_prose()
            code = [line]
        elif not stripped:
            flush_prose()
        elif stripped.startswith("#"):
            flush_prose()
            blocks.append(("prose", line))
        else:
            prose.append(line)

    if code is not None:  # unclosed fence: keep the content, close it per chunk
        blocks.append(("code", "\n".join(code)))
    flush_prose()
    return blocks


class CharacterChunker:
    """Structure-aware character chunks (architecture doc default: 600 / 120)."""

    name = "character"

    def __init__(self, chunk_size: int = 600, overlap: int = 120):
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> list[str]:
        pieces: list[str] = []
        for kind, block in _markdown_blocks(text):
            if kind == "code" and (len(block) > self.chunk_size or not block.rstrip().endswith(FENCE) or block.count("\n") == 0):
                pieces.extend(_split_code(block, self.chunk_size))
            elif len(block) <= self.chunk_size:
                pieces.append(block)
            else:
                pieces.extend(_split_prose(block, self.chunk_size, self.overlap))
        return [chunk for chunk in _merge(pieces, self.chunk_size, self.overlap, "\n\n") if chunk.strip()]


def get_chunker(strategy: str | None = None) -> ChunkingStrategy:
    """Build the chunker selected by ``strategy`` or ``settings.CHUNK_STRATEGY``."""
    strategy = strategy or settings.CHUNK_STRATEGY
    if strategy == "character":
        return CharacterChunker(settings.CHUNK_SIZE_CHARS, settings.CHUNK_OVERLAP_CHARS)
    if strategy == "word":
        return WordChunker(settings.CHUNK_SIZE_WORDS, settings.CHUNK_OVERLAP_WORDS)
    raise ValueError(f"Unknown chunking strategy: {strategy!r}")
