import os
import glob
from typing import Optional

class RAGSystem:
    """
    Encapsulated RAG System.
    Prevents directory reading, indexing, and query execution on module import.
    With robust pure-Python keyword fallback if llama-index is missing or fails.
    """
    def __init__(self, docs_dir: str = "./docs"):
        self.docs_dir = os.path.abspath(docs_dir)
        self._index = None
        self._fallback_mode = False

    @property
    def index(self):
        if self._index is None and not self._fallback_mode:
            if not os.path.exists(self.docs_dir):
                os.makedirs(self.docs_dir, exist_ok=True)
                
            try:
                from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
                documents = SimpleDirectoryReader(self.docs_dir).load_data()
                if not documents:
                    from llama_index.core.schema import Document
                    documents = [Document(text="Empty workspace documentation.")]
                self._index = VectorStoreIndex.from_documents(documents)
            except Exception:
                # Set fallback mode and proceed to custom search
                self._fallback_mode = True
                self._index = None
        return self._index

    def query(self, text: str) -> str:
        """Run a query against the document store, with smart fallback."""
        if not os.path.exists(self.docs_dir):
            return "No documentation directory found."

        if not self._fallback_mode:
            try:
                idx = self.index
                if idx is not None:
                    query_engine = idx.as_query_engine()
                    return str(query_engine.query(text))
            except Exception:
                self._fallback_mode = True

        # Pure-Python keyword/paragraph overlap fallback search
        return self._fallback_query(text)

    def _fallback_query(self, text: str) -> str:
        """
        Pure-Python fallback search to find the most relevant paragraphs
        in local documentation files.
        """
        query_words = [w.lower() for w in text.split() if len(w) > 2]
        if not query_words:
            # Fallback to simple lowercase search for very short queries
            query_words = [text.lower().strip()]

        candidates = []
        extensions = ["*.md", "*.txt", "*.json", "*.py", "*.rst"]
        
        # Scan for matching text files
        for ext in extensions:
            for filepath in glob.glob(os.path.join(self.docs_dir, "**", ext), recursive=True):
                if os.path.isdir(filepath):
                    continue
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        
                    # Split file content into paragraph blocks
                    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
                    if not paragraphs:
                        # Fallback to splitting by line if double newline isn't used
                        paragraphs = [l.strip() for l in content.split("\n") if l.strip()]

                    filename = os.path.relpath(filepath, self.docs_dir)

                    for idx, para in enumerate(paragraphs):
                        para_lower = para.lower()
                        score = 0
                        
                        # Calculate match score based on keyword hits
                        for word in query_words:
                            if word in para_lower:
                                score += 1
                        
                        if score > 0:
                            candidates.append({
                                "file": filename,
                                "paragraph_index": idx + 1,
                                "content": para,
                                "score": score
                            })
                except Exception:
                    pass

        if not candidates:
            # Check if there are any documents in docs_dir at all
            all_files = []
            for ext in extensions:
                all_files.extend(glob.glob(os.path.join(self.docs_dir, "**", ext), recursive=True))
            if not all_files:
                return "No documentation files found in docs/ directory."
            return f"No matching documentation sections found for query: {text}"

        # Sort candidate paragraphs by score descending
        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        # Build matching blocks response
        response_blocks = []
        # Limit to top 3 matching chunks
        for item in candidates[:3]:
            block = f"### [Documentation] {item['file']} (Paragraph {item['paragraph_index']})\n{item['content']}"
            response_blocks.append(block)

        return "\n\n".join(response_blocks)

