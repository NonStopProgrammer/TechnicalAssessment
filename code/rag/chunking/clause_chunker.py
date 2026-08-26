"""RAG-2: chunking strategy.

RAG-2.1: primary split is on detected clause/section numbering, not a fixed
character window blind to structure — regulatory text is dense with
cross-referencing sub-clauses, so a blind window can sever a threshold
number from the clause that qualifies it.

RAG-2.2/2.3: where a clause exceeds the target size, recursively split on
paragraph -> sentence boundaries with ~15% overlap so a number/date at a
boundary isn't lost. Target size (512 tokens) is approximated as ~2048
characters (~4 chars/token for English regulatory prose) to avoid pulling
in a tokenizer dependency for an approximation only used for chunk sizing.

RAG-2.5: this module only ever sees one document's text at a time — chunks
never span two source documents.
"""

import re
from dataclasses import dataclass, field

from langchain_text_splitters import RecursiveCharacterTextSplitter

from shared.models.chunk import Chunk
from shared.models.document import DocumentMetadata

TARGET_CHARS = 2048  # ~512 tokens
OVERLAP_CHARS = 300  # ~15%

# Matches markdown headings with numeric clause prefixes, e.g. "### 6.1 Title",
# and bare "6.1 Title" / "Para 12" lines (RAG-2.1's stated pattern examples).
_HEADING_PATTERN = re.compile(
    r"^(?:#{1,4}\s*)?(?P<label>(?:Para(?:graph)?\.?\s*)?\d+(?:\.\d+)*)\.?\s+(?P<title>.+)$",
    re.MULTILINE,
)


@dataclass
class ClauseSection:
    clause_id: str
    section_path: str
    text: str


@dataclass
class ChunkingResult:
    chunks: list[Chunk] = field(default_factory=list)


def split_into_clauses(text: str) -> list[ClauseSection]:
    """RAG-2.1: regex-based clause boundary detection."""
    matches = list(_HEADING_PATTERN.finditer(text))
    if not matches:
        return [ClauseSection(clause_id="0", section_path="document", text=text.strip())]

    sections: list[ClauseSection] = []
    path_stack: list[str] = []

    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        clause_id = match.group("label").replace("Para", "").replace("Paragraph", "").strip()
        title = match.group("title").strip()
        body = text[start:end].strip()

        depth = clause_id.count(".") + 1
        path_stack = path_stack[: depth - 1]
        path_stack.append(f"{clause_id} {title}".strip())

        sections.append(
            ClauseSection(clause_id=clause_id, section_path=" > ".join(path_stack), text=body)
        )
    return sections


def chunk_document(text: str, metadata: DocumentMetadata) -> list[Chunk]:
    sections = split_into_clauses(text)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=TARGET_CHARS,
        chunk_overlap=OVERLAP_CHARS,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[Chunk] = []
    for section in sections:
        pieces = (
            [section.text]
            if len(section.text) <= TARGET_CHARS
            else splitter.split_text(section.text)  # RAG-2.2 size fallback
        )
        for i, piece in enumerate(pieces):
            suffix = f"-{i}" if len(pieces) > 1 else ""
            chunk_id = f"{metadata.doc_id}::{section.clause_id}{suffix}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    doc_id=metadata.doc_id,
                    clause_id=section.clause_id,
                    section_path=section.section_path,
                    text=piece.strip(),
                    framework=metadata.framework,
                    jurisdiction=metadata.jurisdiction,
                    doc_type=metadata.doc_type,
                    effective_date=metadata.effective_date,
                    version=metadata.version,
                )
            )
    return chunks
