from azure.cosmos import CosmosClient, PartitionKey
from azure.identity import DefaultAzureCredential
from sentence_transformers import SentenceTransformer
import logging

endpoint = "https://documind-cosmos-nna2005.documents.azure.com:443/"

try:

    credential = DefaultAzureCredential()

    client = CosmosClient(endpoint,credential=credential)

    database = client.get_database_client("documind-db")

    container = database.get_container_client("documents-vector")

    model = SentenceTransformer('all-MiniLM-L6-v2')  # 384-dim, matches the policy above

    logging.info("CosmoDB/model initialisatiokn successful")

except Exception as e:
    logging.error(f"Global configuration/model call: {e}")

    


vector_embedding_policy = {
    "vectorEmbeddings":[
        {
            "path": "/embedding",
            "dataType": "float32",
            "jnceFunction": "cosine",
            "dimensions": 384
        }
    ]
}

indexing_policy = {
    "indexingMode": "consistent",
    "automatic": True,
    "includedPaths": [{"path": "/*"}],
    "excludedPaths": [
        {"path": "/\"_etag\"/?"},
        {"path": "/embedding/*"}
    ],
    "vectorIndexes": [
        {"path": "/embedding", "type": "flat"}
    ]
}

container_v3 = database.create_container_if_not_exists(
    id="documents-vector",
    partition_key=PartitionKey(path="/userId"),
    vector_embedding_policy=vector_embedding_policy,
    indexing_policy=indexing_policy
)


docs = [
    {"id": "doc-301", "userId": "user-a", "filename": "invoice-march.pdf",
     "text": "Invoice for consulting services rendered in March, total amount due"},
    {"id": "doc-302", "userId": "user-a", "filename": "employment-contract.pdf",
     "text": "Employment agreement outlining salary, benefits, and termination clauses"},
    {"id": "doc-303", "userId": "user-a", "filename": "invoice-april.pdf",
     "text": "Invoice for professional services in April, payment terms net 30"},
]

for doc in docs:
    doc["embedding"] = model.encode(doc["text"]).tolist()
    container_v3.create_item(doc)
    
    
query_text = "billing document for services provided"
query_vector = model.encode(query_text).tolist()

results = list(container_v3.query_items(
    query="""SELECT TOP 3 c.id, c.filename, VectorDistance(c.embedding, @qv) AS score
              FROM c
              ORDER BY VectorDistance(c.embedding, @qv)""",
    parameters=[{"name": "@qv", "value": query_vector}],
    enable_cross_partition_query=True
))

for r in results:
    print(r["filename"], "-", r["score"])