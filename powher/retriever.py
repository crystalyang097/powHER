"""RAG retrieval over the corpus/ evidence base.

Corpus files are chunked on `##` headers. Every chunk carries the
source_id declared at the top of its file, so retrieved chunks can be
cited in the UI and checked against by guardrails.py.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus"
CHROMA_DIR = Path(__file__).resolve().parent.parent / ".chroma"
COLLECTION_NAME = "powher_corpus"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


@dataclass
class Chunk:
    chunk_id: str
    text: str
    source_id: str
    source_file: str
    heading: str


def _parse_corpus_file(path: Path) -> list[Chunk]:
    text = path.read_text()
    source_id_match = re.search(r"^source_id:\s*(\S+)", text, re.MULTILINE)
    source_id = source_id_match.group(1) if source_id_match else path.stem.upper()

    sections = re.split(r"^## (.+)$", text, flags=re.MULTILINE)
    chunks: list[Chunk] = []
    # sections[0] is the preamble before the first "##" (title + source_id line) -- skip it.
    for i in range(1, len(sections), 2):
        heading = sections[i].strip()
        body = sections[i + 1].strip()
        chunk_id = f"{path.stem}::{heading}"
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                text=f"## {heading}\n\n{body}",
                source_id=source_id,
                source_file=path.name,
                heading=heading,
            )
        )
    return chunks


def load_corpus_chunks(corpus_dir: Path = CORPUS_DIR) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(corpus_dir.glob("*.md")):
        if path.name == "SOURCES.md":
            continue
        chunks.extend(_parse_corpus_file(path))
    return chunks


class Retriever:
    def __init__(self, persist_dir: Path = CHROMA_DIR, corpus_dir: Path = CORPUS_DIR):
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME, embedding_function=self._embedding_fn
        )
        self._corpus_dir = corpus_dir
        if self._collection.count() == 0:
            self._index()

    def _index(self) -> None:
        chunks = load_corpus_chunks(self._corpus_dir)
        if not chunks:
            return
        self._collection.add(
            ids=[c.chunk_id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[
                {"source_id": c.source_id, "source_file": c.source_file, "heading": c.heading}
                for c in chunks
            ],
        )

    def reindex(self) -> None:
        self._client.delete_collection(COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME, embedding_function=self._embedding_fn
        )
        self._index()

    def query(
        self, query_text: str, n_results: int = 4, exclude_phase: bool = False
    ) -> list[Chunk]:
        """Return the top-n cited chunks relevant to query_text.

        If exclude_phase is True (cycle_applicable=False path), phase-evidence
        and phase-education chunks are filtered out so phase context never
        leaks into the model's grounding.
        """
        where = None
        if exclude_phase:
            where = {"source_id": {"$nin": ["PHASE-EVIDENCE", "PHASE-EDUCATION"]}}
        results = self._collection.query(
            query_texts=[query_text], n_results=n_results, where=where
        )
        chunks: list[Chunk] = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        for chunk_id, doc, meta in zip(ids, docs, metas):
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    text=doc,
                    source_id=meta["source_id"],
                    source_file=meta["source_file"],
                    heading=meta["heading"],
                )
            )
        return chunks


_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever
