import os
from typing import Optional

class RAGSystem:
    """
    Encapsulated RAG System.
    Prevents directory reading, indexing, and query execution on module import.
    """
    def __init__(self, docs_dir: str = "./docs"):
        self.docs_dir = os.path.abspath(docs_dir)
        self._index = None

    @property
    def index(self):
        if self._index is None:
            if not os.path.exists(self.docs_dir):
                os.makedirs(self.docs_dir, exist_ok=True)
                
            try:
                from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
            except ImportError:
                raise ImportError(
                    "The 'llama-index' library is missing in your current environment.\n"
                    "To install it, run:\n"
                    "  pip install llama-index\n"
                )
                
            documents = SimpleDirectoryReader(self.docs_dir).load_data()
            if not documents:
                # Handle empty directory gracefully
                try:
                    from llama_index.core.schema import Document
                except ImportError:
                    raise ImportError(
                        "The 'llama-index' library is missing in your current environment.\n"
                        "To install it, run:\n"
                        "  pip install llama-index\n"
                    )
                documents = [Document(text="Empty workspace documentation.")]
            self._index = VectorStoreIndex.from_documents(documents)
        return self._index


    def query(self, text: str) -> str:
        """Run a query against the document store."""
        query_engine = self.index.as_query_engine()
        return str(query_engine.query(text))

