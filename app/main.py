from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models import Link
from app.schemas import LinkResponse, ShortenRequest
from app.shortcode import generate_code

app = FastAPI(title="Shortener", version="0.1.0")

# _links: dict[str, str] = {} added the db so no need for this


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "hello kali"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/shorten", response_model=LinkResponse)
async def shorten(
    payload: ShortenRequest,
    db: AsyncSession = Depends(get_db),
) -> LinkResponse:
    url = str(payload.url)

    # try few times in case of rare collisions
    for _ in range(5):
        code = generate_code()
        link = Link(code=code, url=url)
        db.add(link)

        try:
            await db.commit()
            await db.refresh(link)
            break
        except IntegrityError:
            await db.rollback()
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate unique code",
        )

    return LinkResponse(
        code=link.code,
        url=link.url,
        short_url=f"{settings.base_url}/{link.code}",
        clicks=link.clicks,
        created_at=link.created_at,
    )


@app.get("/{code}")
async def redirect(
    code: str,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    link = await db.scalar(select(Link).where(Link.code == code))
    if link is None:
        raise HTTPException(status_code=404, detail="Short code not found")

    await db.execute(update(Link).where(Link.id == link.id).values(clicks=Link.clicks + 1))
    await db.commit()

    return RedirectResponse(url=link.url, status_code=302)
