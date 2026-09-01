from fastapi import FastAPI

app = FastAPI(
    title="Gaming Wallet Gateway",
    description="Sanitized FastAPI reference implementation of a high-throughput gaming wallet gateway.",
    version="1.0.0",
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}