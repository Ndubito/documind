import psycopg2 
from psycopg2.extras import execute_values
from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer('all-MiniLM-L6-v2')

connections = []

try:
    for i in range(100):
        conn = psycopg2.connect(
        host='documind-pg-nna2005.postgres.database.azure.com',
        dbname='postgres',
        user='dimgranola5',
        password='Its21achars',
        sslmode='require'
        )
        connections.append(conn)
        print(f"Connection {i+1} opened")
except Exception as e:
    print(f"Failed at connection {len(connections) + 1}: {e}")

finally:
    for c in connections:
        c.close()



# cur = conn.cursor()

# Generate 10,000 random 384-dim vectors — real semantic meaning doesn't matter here,
# we're measuring build/query mechanics, not relevance
# np.random.seed(42)
# rows = [
#     (f"synthetic-{i}.pdf", "synthetic benchmark content", np.random.rand(384).tolist())
#     for i in range(10000)
# ]

# execute_values(
#     cur,
#     "INSERT INTO documents (filename, content, embedding) VALUES %s",
#     rows,
#     template="(%s, %s, %s::vector)"
# )

# conn.commit()

# print("Inserted: ", len(rows))

