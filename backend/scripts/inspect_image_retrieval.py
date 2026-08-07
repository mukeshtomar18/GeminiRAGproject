from app.clients.gemini import GeminiClient
from app.clients.pinecone_client import PineconeClient
from app.core.config import get_settings

s = get_settings()
p = PineconeClient(s)
g = GeminiClient(s)
v = g.embed_text("person wearing red t-shirt image photo")

print("UNFILTERED")
for c in p.query(v, top_k=8):
    preview = (c.text_preview or "")[:90].replace("\n", " ")
    print(c.modality, round(c.score, 3), c.title, preview, "url=", c.file_url)

print("--- IMAGE FILTER ---")
idx = p._require()
res = idx.query(
    vector=v,
    top_k=8,
    include_metadata=True,
    namespace=s.pinecone_namespace,
    filter={"modality": {"$eq": "image"}},
)
matches = getattr(res, "matches", None) or []
print("count", len(matches))
for m in matches:
    meta = getattr(m, "metadata", None) or {}
    preview = str(meta.get("text_preview", ""))[:90].replace("\n", " ")
    print(
        meta.get("modality"),
        round(float(getattr(m, "score", 0) or 0), 3),
        meta.get("title"),
        preview,
        meta.get("file_url"),
    )
