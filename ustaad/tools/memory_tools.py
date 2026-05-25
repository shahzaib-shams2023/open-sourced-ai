import chromadb
import uuid

client = chromadb.PersistentClient(
    path="./memory"
)

collection = client.get_or_create_collection(
    name="local_ai_memory"
)

def save_memory(text):

    collection.add(
        documents=[text],
        ids=[str(uuid.uuid4())]
    )

def search_memory(query, limit=5):

    results = collection.query(
        query_texts=[query],
        n_results=limit
    )

    return results
