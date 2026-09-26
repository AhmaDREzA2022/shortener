from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse

from app.schemas import ShortenRequest

app = FastAPI(title="Shortener", version="0.1.0")

_links: dict[str, str] = {}


@app.get("/")
def root() -> dict[str, str]:
    return {"messages": "Hello world"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/shorten")
def shorten(payload: ShortenRequest) -> dict[str, str]:
    code = "abc123"
    _links[code] = str(payload.url)
    return {"code": code, "url": str(payload.url)}


@app.get("/{code}")
def redirect(code: str) -> RedirectResponse:
    url = _links.get(code)
    if url is None:
        raise HTTPException(status_code=404, detail="Short code not found")
    return RedirectResponse(url=url, status_code=302)
