from fastapi import FastAPI

app = FastAPI(title="Shortener", version="0.1.0")

@app.get("/")
def root() -> dict[str, str]:
    return {"messages": "Hello world"}

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
