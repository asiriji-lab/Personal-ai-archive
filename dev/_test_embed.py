import requests, time

s = time.time()
r = requests.post(
    "http://localhost:11434/api/embed",
    json={"model": "nomic-embed-text", "input": "test embedding"},
    timeout=120,
)
elapsed = time.time() - s
print(f"Status: {r.status_code}, Time: {elapsed:.1f}s")
if r.ok:
    d = r.json()
    dims = len(d.get("embeddings", [[]])[0])
    print(f"Embedding dims: {dims}")
else:
    print(f"Error: {r.text[:200]}")
