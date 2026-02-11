"""
cast_parser.py — Context-Aware Splitting (cAST) using Tree-sitter.

Extracts structured code units (methods, functions) from Java and TypeScript
source files, preserving associated Javadoc/JSDoc comments for RAG ingestion.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from tree_sitter_language_pack import get_language, get_parser


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class CodeChunk(BaseModel):
    """A single extracted code unit with metadata."""
    name: str
    language: str
    body: str
    docstring: str = ""
    start_line: int = 0
    end_line: int = 0
    file_path: str = ""
    chunk_type: str = "method"  # method | function | class


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node_text(source_bytes: bytes, node) -> str:
    """Extract text content from a tree-sitter node."""
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _is_trivial_getter_setter(name: str, body_text: str) -> bool:
    """
    Heuristic: skip simple getters/setters.
    A method is considered trivial if:
      - Its name starts with get/set/is AND
      - Its body has <= 2 statements (roughly: <= 2 semicolons inside braces)
    """
    lower_name = name.lower()
    if not any(lower_name.startswith(prefix) for prefix in ("get", "set", "is")):
        return False
    # Count semicolons as a proxy for statement count
    semicolons = body_text.count(";")
    return semicolons <= 2


def _find_preceding_comment(source_bytes: bytes, node) -> str:
    """
    Walk backwards through siblings to find a Javadoc / block comment
    immediately preceding the given node.
    """
    prev = node.prev_named_sibling
    if prev is None:
        return ""

    comment_types = {"block_comment", "line_comment", "comment"}
    if prev.type in comment_types:
        text = _node_text(source_bytes, prev)
        # Only return if it looks like Javadoc / JSDoc
        if text.strip().startswith("/**") or text.strip().startswith("//"):
            return text.strip()
    return ""


# ---------------------------------------------------------------------------
# Java Extraction
# ---------------------------------------------------------------------------

def extract_java_methods(
    file_content: str,
    file_path: str = "",
) -> list[CodeChunk]:
    """
    Parse Java source code and extract method declarations with their
    associated Javadoc comments.  Skips trivial getters/setters.

    Args:
        file_content: Raw Java source code as a string.
        file_path:    Optional file path for metadata.

    Returns:
        List of CodeChunk objects, one per extracted method.
    """
    parser = get_parser("java")
    language = get_language("java")

    source_bytes = file_content.encode("utf-8")
    tree = parser.parse(source_bytes)

    chunks: list[CodeChunk] = []

    # Query for method declarations
    query = language.query("(method_declaration) @method")
    matches = query.matches(tree.root_node)

    for _pattern_idx, match_dict in matches:
        for node in match_dict.get("method", []):
            body_text = _node_text(source_bytes, node)

            # Extract method name
            name_node = node.child_by_field_name("name")
            method_name = _node_text(source_bytes, name_node) if name_node else "unknown"

            # Skip trivial getters/setters
            if _is_trivial_getter_setter(method_name, body_text):
                continue

            docstring = _find_preceding_comment(source_bytes, node)

            chunks.append(CodeChunk(
                name=method_name,
                language="java",
                body=body_text,
                docstring=docstring,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                file_path=file_path,
                chunk_type="method",
            ))

    return chunks


# ---------------------------------------------------------------------------
# TypeScript Extraction
# ---------------------------------------------------------------------------

def extract_typescript_functions(
    file_content: str,
    file_path: str = "",
) -> list[CodeChunk]:
    """
    Parse TypeScript source code and extract function/method declarations
    with their associated JSDoc comments.

    Args:
        file_content: Raw TypeScript source code.
        file_path:    Optional file path for metadata.

    Returns:
        List of CodeChunk objects.
    """
    parser = get_parser("typescript")
    language = get_language("typescript")

    source_bytes = file_content.encode("utf-8")
    tree = parser.parse(source_bytes)

    chunks: list[CodeChunk] = []

    # Capture function declarations and method definitions
    query_text = """
    (function_declaration) @func
    (method_definition) @method
    (lexical_declaration
      (variable_declarator
        value: (arrow_function) @arrow))
    """
    query = language.query(query_text)
    matches = query.matches(tree.root_node)

    for _pattern_idx, match_dict in matches:
        for capture_name, nodes in match_dict.items():
            for node in nodes:
                body_text = _node_text(source_bytes, node)

                # Determine name based on node type
                if capture_name == "arrow":
                    # For arrow functions, the parent declarator has the name
                    parent = node.parent
                    name_node = parent.child_by_field_name("name") if parent else None
                else:
                    name_node = node.child_by_field_name("name")

                func_name = _node_text(source_bytes, name_node) if name_node else "anonymous"
                docstring = _find_preceding_comment(source_bytes, node)

                chunk_type = "method" if capture_name == "method" else "function"

                chunks.append(CodeChunk(
                    name=func_name,
                    language="typescript",
                    body=body_text,
                    docstring=docstring,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    file_path=file_path,
                    chunk_type=chunk_type,
                ))

    return chunks


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

def parse_file(file_content: str, file_path: str) -> list[CodeChunk]:
    """
    Auto-detect language from file extension and extract code chunks.

    Args:
        file_content: The raw file content.
        file_path:    Path to the file (used for language detection).

    Returns:
        List of extracted CodeChunks.
    """
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""

    if ext == "java":
        return extract_java_methods(file_content, file_path)
    elif ext in ("ts", "tsx"):
        return extract_typescript_functions(file_content, file_path)
    else:
        return []
