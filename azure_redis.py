import redis
import numpy as np
from redis.commands.search.field import TextField, VectorField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from sentence_transformers import SentenceTransformer
import os
from dotenv import load_dotenv

load_dotenv()


model = SentenceTransformer('all-MiniLM-L6-v2')

r = redis.Redis(
    host="documind-redis.southafricanorth.redis.azure.net",
    port=10000,
    password=os.getenv("REDIS_PASSWORD"),
    ssl=True
)

#define the index schema
schema=(
    TextField("filename"),
    VectorField("embedding", "HNSW", {
        "TYPE": "FLOAT32",
        "DIM": 384,
        "DISTANCE_METRIC": "COSINE"
    })
)

r.ft("idx:documents").create_index(
    schema,
    definition=IndexDefinition(prefix=["doc:"], index_type=IndexType.HASH)
)

# Same three documents as Cosmos DB / Postgres
docs = [
    ("invoice-march.pdf", "Invoice for consulting services rendered in March, total amount due"),
    ("employment-contract.pdf", "Employment agreement outlining salary, benefits, and termination clauses"),
    ("invoice-april.pdf", "Invoice for professional services in April, payment terms net 30"),
]

for i, (filename, text) in enumerate(docs):
    embedding_bytes = model.encode(text).astype(np.float32).tobytes()
    r.hset(f"doc:{i}", mapping={"filename": filename, "embedding": embedding_bytes})

#Query — same query text used in the Cosmos DB session
query_text = "billing document for services provided"
query_vector = model.encode(query_text).astype(np.float32).tobytes()

q = (
    Query("*=>[KNN 3 @embedding $vec AS score]")
    .sort_by("score")
    .return_fields("filename", "score")
    .dialect(2)
)

results = r.ft("idx:documents").search(q, query_params={"vec": query_vector})

for doc in results.docs:
    print(doc.filename, "-", doc.score)