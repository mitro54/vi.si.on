"""
ChromaDB-powered Local Knowledge Base with file-watcher auto-ingestion.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..config import KnowledgeBaseConfig, get_default_data_dir


@dataclass
class KnowledgeChunk:
    content: str
    source: str
    score: float


class _FileWatcherHandler(FileSystemEventHandler):
    """Watches configured folder and triggers file ingestion upon changes."""

    def __init__(self, kb: KnowledgeBase):
        self.kb = kb

    def on_created(self, event):
        if not event.is_directory:
            self.kb.ingest_file(Path(event.src_path))

    def on_modified(self, event):
        if not event.is_directory:
            self.kb.ingest_file(Path(event.src_path))

    def on_deleted(self, event):
        if not event.is_directory:
            self.kb.delete_file(Path(event.src_path))


class KnowledgeBase:
    """Manages ChromaDB vector store and directory ingestion."""

    SUPPORTED_EXTENSIONS = {".txt", ".md", ".py", ".json", ".csv", ".html", ".log", ".rst", ".yaml", ".yml"}

    def __init__(self, config: KnowledgeBaseConfig):
        self.config = config
        persist_dir = config.persist_directory
        if not persist_dir:
            persist_dir = str(get_default_data_dir() / "chroma_db")

        os.makedirs(persist_dir, exist_ok=True)
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="ambient_knowledge",
            metadata={"hnsw:space": "cosine"}
        )

        self._observer: Optional[Observer] = None
        if config.enabled and config.watch_directory:
            watch_path = Path(config.watch_directory)
            if watch_path.exists() and watch_path.is_dir():
                self.ingest_directory(watch_path)
                self._start_watcher(watch_path)

    def _start_watcher(self, directory: Path) -> None:
        """Starts background file system observer."""
        try:
            self._observer = Observer()
            handler = _FileWatcherHandler(self)
            self._observer.schedule(handler, str(directory), recursive=True)
            self._observer.daemon = True
            self._observer.start()
        except Exception as e:
            print(f"[KnowledgeBase] Failed to start watchdog observer: {e}")

    def stop_watcher(self) -> None:
        """Stops background file system observer."""
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=2.0)
            except Exception:
                pass

    def _chunk_text(self, text: str, chunk_size: int = 600, overlap: int = 100) -> List[str]:
        """Splits document text into overlapping segments."""
        if not text.strip():
            return []
        chunks = []
        start = 0
        text_len = len(text)
        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= text_len:
                break
            start += chunk_size - overlap
        return chunks

    def ingest_file(self, file_path: Path) -> None:
        """Reads, chunks, and indexes a single file."""
        if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            return

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            chunks = self._chunk_text(content)
            if not chunks:
                return

            # First clear any existing chunks from this file
            file_key = str(file_path.resolve())
            self.delete_file(file_path)

            ids = [f"{file_key}__chunk_{i}" for i in range(len(chunks))]
            metadatas = [{"source": file_key, "filename": file_path.name, "chunk_index": i} for i in range(len(chunks))]

            self.collection.add(
                documents=chunks,
                ids=ids,
                metadatas=metadatas
            )
        except Exception as e:
            print(f"[KnowledgeBase] Failed to ingest {file_path}: {e}")

    def delete_file(self, file_path: Path) -> None:
        """Removes all indexed chunks for the given file."""
        try:
            file_key = str(file_path.resolve())
            self.collection.delete(where={"source": file_key})
        except Exception:
            pass

    def ingest_directory(self, directory: Path) -> None:
        """Recursively ingests all supported documents in a folder."""
        for root, _, files in os.walk(directory):
            for file in files:
                p = Path(root) / file
                self.ingest_file(p)

    def query(self, query_text: str, top_k: Optional[int] = None) -> List[KnowledgeChunk]:
        """Retrieves top_k relevant snippets from vector index."""
        if not self.config.enabled:
            return []

        k = top_k or self.config.top_k
        try:
            res = self.collection.query(
                query_texts=[query_text],
                n_results=k
            )

            documents = res.get("documents", [[]])[0]
            metadatas = res.get("metadatas", [[]])[0]
            distances = res.get("distances", [[]])[0]

            results = []
            for doc, meta, dist in zip(documents, metadatas, distances):
                results.append(
                    KnowledgeChunk(
                        content=doc,
                        source=meta.get("filename", "unknown"),
                        score=float(dist) if dist is not None else 0.0
                    )
                )
            return results
        except Exception as e:
            return []

    def format_context_for_prompt(self, query_text: str) -> str:
        """Returns contextual snippet string to append to system messages."""
        chunks = self.query(query_text)
        if not chunks:
            return ""
        items = [f"--- Document: {c.source} ---\n{c.content}" for c in chunks]
        return "\n\nRelevant Context from User Knowledge Base:\n" + "\n\n".join(items)

    @staticmethod
    def get_tool_schema() -> Dict[str, Any]:
        """Tool definition for explicit knowledge base search."""
        return {
            "type": "function",
            "function": {
                "name": "search_knowledge_base",
                "description": "Search user's local documents, notes, and codebase for matching knowledge.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search keywords or semantic question to look up",
                        }
                    },
                    "required": ["query"],
                },
            },
        }
