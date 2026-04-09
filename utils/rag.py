import re
from typing import List


def chunk_by_paragraphs(text: str) -> List[str]:
    return rag_text_by_regex(r"\n\s*\n", text)


def chunk_by_sentences(text: str) -> List[str]:
    return rag_text_by_regex(r"(?<=[。！？.?!])\s+", text)


def chunk_by_markdown_headers(text: str) -> List[str]:
    return rag_text_by_regex(r"\n(?=#{1,6}\s)", text, keep_separator=True)


def chunk_by_fixed_size(
    text: str, chunk_size: int = 500, overlap: int = 50
) -> List[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            match = re.search(r"[。！？.!?\n]", text[end - 20 : end + 20])
            if match:
                end = end - 20 + match.end()

        chunks.append(text[start:end].strip())
        start = end - overlap

    return chunks


def rag_text_by_regex(
    pattern: str, text: str, keep_separator: bool = False
) -> List[str]:
    if not text or not pattern:
        return [text] if text else []

    if keep_separator:
        pattern = f"({pattern})"
        chunks = re.split(pattern, text)

        result = []
        for i in range(0, len(chunks) - 1, 2):
            if chunks[i] or chunks[i + 1]:
                result.append(
                    chunks[i] + (chunks[i + 1] if i + 1 < len(chunks) else "")
                )
        if len(chunks) % 2 == 1 and chunks[-1]:
            result.append(chunks[-1])
    else:
        result = re.split(pattern, text)

    return [chunk.strip() for chunk in result if chunk and chunk.strip()]
