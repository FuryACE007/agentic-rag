"""
chunker.py — Semantic chunking for code and documentation.

Merges small code chunks into larger semantic units and splits documentation
on structural boundaries (headers, paragraphs) for optimal RAG retrieval.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.ingestion.cast_parser import CodeChunk


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class SemanticChunk(BaseModel):
    """A chunk ready for embedding and storage in the vector database."""
    id: str                          # Unique identifier
    content: str                     # The text content to embed
    chunk_type: str = "code"         # "code" | "doc"
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Code Chunker
# ---------------------------------------------------------------------------

class CodeChunker:
    """
    Merges adjacent small CodeChunks from the same file into larger
    semantic units, respecting a configurable token limit.
    """

    def __init__(self, max_chars: int = 2048, overlap_chars: int = 200) -> None:
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def chunk(self, code_chunks: list[CodeChunk]) -> list[SemanticChunk]:
        """
        Merge small code chunks from the same file into larger units.

        Args:
            code_chunks: Parsed CodeChunk objects from cast_parser.

        Returns:
            List of SemanticChunks ready for embedding.
        """
        if not code_chunks:
            return []

        # Group by file
        by_file: dict[str, list[CodeChunk]] = {}
        for chunk in code_chunks:
            by_file.setdefault(chunk.file_path, []).append(chunk)

        semantic_chunks: list[SemanticChunk] = []

        for file_path, file_chunks in by_file.items():
            # Sort by start line
            file_chunks.sort(key=lambda c: c.start_line)

            current_buffer: list[str] = []
            current_length = 0
            chunk_idx = 0

            for fc in file_chunks:
                # Build a text representation including docstring
                text_parts = []
                if fc.docstring:
                    text_parts.append(fc.docstring)
                text_parts.append(fc.body)
                entry_text = "\n".join(text_parts)

                if current_length + len(entry_text) > self.max_chars and current_buffer:
                    # Flush current buffer
                    semantic_chunks.append(SemanticChunk(
                        id=f"{file_path}::chunk_{chunk_idx}",
                        content="\n\n".join(current_buffer),
                        chunk_type="code",
                        metadata={
                            "file_path": file_path,
                            "language": fc.language,
                            "type": "code",
                            "chunk_index": chunk_idx,
                        },
                    ))
                    chunk_idx += 1
                    current_buffer = []
                    current_length = 0

                current_buffer.append(entry_text)
                current_length += len(entry_text)

            # Flush remaining
            if current_buffer:
                semantic_chunks.append(SemanticChunk(
                    id=f"{file_path}::chunk_{chunk_idx}",
                    content="\n\n".join(current_buffer),
                    chunk_type="code",
                    metadata={
                        "file_path": file_path,
                        "language": file_chunks[0].language if file_chunks else "unknown",
                        "type": "code",
                        "chunk_index": chunk_idx,
                    },
                ))

        return semantic_chunks


# ---------------------------------------------------------------------------
# Document Chunker
# ---------------------------------------------------------------------------

class DocumentChunker:
    """
    Splits documentation (Markdown, HTML, plain text) on structural
    boundaries — headers, paragraphs, horizontal rules — for optimal
    retrieval granularity.
    """

    def __init__(self, max_chars: int = 1500, overlap_chars: int = 150) -> None:
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def chunk(
        self,
        content: str,
        source: str = "",
        file_type: str = "md",
    ) -> list[SemanticChunk]:
        """
        Split document content into semantic chunks.

        Args:
            content:   The raw document text.
            source:    Source identifier for metadata.
            file_type: The document format (md, html, txt).

        Returns:
            List of SemanticChunks.
        """
        if not content.strip():
            return []

        sections = self._split_on_headers(content)
        semantic_chunks: list[SemanticChunk] = []

        for idx, section in enumerate(sections):
            # Further split if section exceeds max_chars
            if len(section) <= self.max_chars:
                semantic_chunks.append(SemanticChunk(
                    id=f"{source}::doc_{idx}",
                    content=section.strip(),
                    chunk_type="doc",
                    metadata={
                        "source": source,
                        "file_type": file_type,
                        "type": "doc",
                        "section_index": idx,
                    },
                ))
            else:
                sub_chunks = self._split_by_length(section, source, idx)
                semantic_chunks.extend(sub_chunks)

        return semantic_chunks

    def _split_on_headers(self, content: str) -> list[str]:
        """Split Markdown content on header boundaries (# lines)."""
        lines = content.split("\n")
        sections: list[str] = []
        current: list[str] = []

        for line in lines:
            stripped = line.strip()
            # Split on Markdown headers or horizontal rules
            if (stripped.startswith("#") or stripped in ("---", "***", "___")) and current:
                sections.append("\n".join(current))
                current = []
            current.append(line)

        if current:
            sections.append("\n".join(current))

        return sections

    def _split_by_length(
        self,
        text: str,
        source: str,
        section_idx: int,
    ) -> list[SemanticChunk]:
        """Split a long section into overlapping chunks by character count."""
        chunks: list[SemanticChunk] = []
        start = 0
        sub_idx = 0

        while start < len(text):
            end = min(start + self.max_chars, len(text))

            # Try to break at a paragraph boundary
            if end < len(text):
                last_break = text.rfind("\n\n", start, end)
                if last_break > start:
                    end = last_break

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(SemanticChunk(
                    id=f"{source}::doc_{section_idx}_{sub_idx}",
                    content=chunk_text,
                    chunk_type="doc",
                    metadata={
                        "source": source,
                        "type": "doc",
                        "section_index": section_idx,
                        "sub_index": sub_idx,
                    },
                ))
                sub_idx += 1

            start = end - self.overlap_chars if end < len(text) else len(text)

        return chunks


# ---------------------------------------------------------------------------
# Unified Chunker
# ---------------------------------------------------------------------------

class SemanticChunkerPipeline:
    """
    Unified pipeline that delegates to CodeChunker or DocumentChunker
    based on content type.
    """

    def __init__(
        self,
        code_max_chars: int = 2048,
        doc_max_chars: int = 1500,
    ) -> None:
        self.code_chunker = CodeChunker(max_chars=code_max_chars)
        self.doc_chunker = DocumentChunker(max_chars=doc_max_chars)

    def chunk_code(self, code_chunks: list[CodeChunk]) -> list[SemanticChunk]:
        """Chunk parsed code units."""
        return self.code_chunker.chunk(code_chunks)

    def chunk_document(
        self,
        content: str,
        source: str = "",
        file_type: str = "md",
    ) -> list[SemanticChunk]:
        """Chunk a documentation file."""
        return self.doc_chunker.chunk(content, source, file_type)
