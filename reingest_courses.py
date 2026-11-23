"""Re-ingest generated courses into Qdrant with the configured chunker.

Each lesson's old chunks are deleted (by course title + step id) before the
new ones are upserted with deterministic uuid5 point IDs, so running this
twice leaves the same points behind, and legacy word-based or hash()-ID
chunks for those lessons are removed.

Usage:
    .venv\\Scripts\\python reingest_courses.py                 # every course
    .venv\\Scripts\\python reingest_courses.py --course <id>   # one course folder
    .venv\\Scripts\\python reingest_courses.py --dry-run       # chunk counts only, no Qdrant
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from app.core.config import settings
from app.core.course_paths import ROADMAP_FILENAME, lesson_filename
from app.services.chunking import get_chunker

logger = logging.getLogger("reingest")


@dataclass
class CourseReport:
    course_id: str
    course_title: str = ""
    lessons_ingested: int = 0
    chunks: int = 0
    missing_lessons: list[str] = field(default_factory=list)
    error: str | None = None


def strip_lesson_header(text: str, section_title: str, step_title: str) -> str:
    """Remove the '# section / ## step' header the pipeline adds when saving.

    The pipeline ingests the lesson body without it, so re-ingestion does the same.
    """
    header = f"# {section_title}\n## {step_title}\n\n"
    normalized = text.replace("\r\n", "\n")
    return normalized[len(header):] if normalized.startswith(header) else normalized


def course_ids(base_dir: Path) -> list[str]:
    if not base_dir.is_dir():
        return []
    return sorted(p.name for p in base_dir.iterdir() if (p / ROADMAP_FILENAME).is_file())


def reingest_course(
    course_path: Path,
    ingest: Callable[..., None] | None,
    chunk_counter: Callable[[str], int],
) -> CourseReport:
    """Ingest every saved lesson of one course. ``ingest=None`` means dry run."""
    report = CourseReport(course_id=course_path.name)
    with open(course_path / ROADMAP_FILENAME, encoding="utf-8") as f:
        roadmap = json.load(f)
    report.course_title = roadmap["course_title"]

    for section in roadmap.get("sections", []):
        for step in section.get("steps", []):
            lesson_path = course_path / lesson_filename(step["step_id"], step["step_title"])
            if not lesson_path.is_file():
                report.missing_lessons.append(step["step_id"])
                continue
            body = strip_lesson_header(
                lesson_path.read_text(encoding="utf-8"), section["section_title"], step["step_title"]
            )
            if ingest is not None:
                ingest(
                    course_title=report.course_title,
                    section_title=section["section_title"],
                    step_id=step["step_id"],
                    step_title=step["step_title"],
                    content=body,
                )
            report.lessons_ingested += 1
            report.chunks += chunk_counter(body)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--course", action="append", help="course folder name (repeatable)")
    parser.add_argument("--base-dir", default=str(settings.GENERATED_COURSES_DIR))
    parser.add_argument("--dry-run", action="store_true", help="count chunks without touching Qdrant")
    parser.add_argument(
        "--recreate-collection",
        action="store_true",
        help="delete and rebuild the collection when its vector size differs from the embedding model "
        "(removes every stored chunk, including courses not re-ingested in this run)",
    )
    args = parser.parse_args(argv)
    if args.dry_run and args.recreate_collection:
        parser.error("--dry-run and --recreate-collection cannot be combined")

    base_dir = Path(args.base_dir)
    available = course_ids(base_dir)
    selected = args.course or available
    unknown = [c for c in selected if c not in available]
    if unknown:
        print(f"Unknown course folder(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    chunker = get_chunker()
    ingest = None
    if not args.dry_run:
        from Generate_Course import ensure_collection, ingest_lesson_to_qdrant_with_retry
        from app.services.vector_store import CollectionDimensionError

        try:
            action = ensure_collection(recreate=args.recreate_collection)
        except CollectionDimensionError as error:
            print(str(error), file=sys.stderr)
            return 3
        print(f"Collection {settings.COLLECTION_NAME!r}: {action}")
        ingest = ingest_lesson_to_qdrant_with_retry

    from app.services.embeddings import get_embedder

    embedder = get_embedder()
    print(
        f"Chunker: {chunker.name} | embeddings: {embedder.name}:{embedder.model} ({embedder.dimensions} dims) "
        f"| courses: {len(selected)} | {'dry run' if args.dry_run else 'writing to Qdrant'}"
    )
    failed = False
    for cid in selected:
        try:
            report = reingest_course(base_dir / cid, ingest, lambda text: len(chunker.split(text)))
        except Exception as error:
            logger.exception("Re-ingesting %s failed", cid)
            print(f"FAILED  {cid}: {type(error).__name__}: {error}")
            failed = True
            continue
        missing = f", missing lessons: {', '.join(report.missing_lessons)}" if report.missing_lessons else ""
        print(f"OK      {cid}: {report.lessons_ingested} lessons, {report.chunks} chunks{missing}")
    return 1 if failed else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    sys.exit(main())
