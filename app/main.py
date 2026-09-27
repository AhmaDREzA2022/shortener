from pathlib import Path
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models import Link, User
from app.schemas import LinkResponse, ShortenForm, ShortenRequest, UserCreate, UserResponse
from app.security import hash_password
from app.shortcode import generate_code

BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Shortener", version="0.1.0")

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


async def _create_link(url: str, db: AsyncSession) -> Link:
    for _ in range(5):
        link = Link(code=generate_code(), url=url)
        db.add(link)
        try:
            await db.commit()
            await db.refresh(link)
            return link
        except IntegrityError:
            await db.rollback()
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Could not generate unique code",
    )


# _links: dict[str, str] = {} added the db so no need for this


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    result = await db.scalars(select(Link).order_by(Link.id.desc()).limit(50))
    links = result.all()
    return templates.TemplateResponse(request=request, name="index.html", context={"links": links})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/shorten", response_class=HTMLResponse)
async def shorten_html(
    request: Request,
    form: Annotated[ShortenForm, Form()],
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    link = await _create_link(str(form.url), db)
    return templates.TemplateResponse(
        request=request,
        name="_link_row.html",
        context={"link": link},
    )


@app.post("/api/shorten", response_model=LinkResponse, tags=["api"])
async def shorten(
    payload: ShortenRequest,
    db: AsyncSession = Depends(get_db),
) -> LinkResponse:
    link = await _create_link(str(payload.url), db)
    return LinkResponse(
        code=link.code,
        url=link.url,
        short_url=f"{settings.base_url}/{link.code}",
        clicks=link.clicks,
        created_at=link.created_at,
    )


@app.get("/api/links", response_model=list[LinkResponse], tags=["api"])
async def list_links(
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
) -> list[LinkResponse]:
    result = await db.scalars(select(Link).order_by(Link.id.desc()).limit(limit))
    links = result.all()
    return [
        LinkResponse(
            code=link.code,
            url=link.url,
            short_url=f"{settings.base_url}/{link.code}",
            clicks=link.clicks,
            created_at=link.created_at,
        )
        for link in links
    ]


@app.post(
    "/api/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["auth"]
)
async def signup(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    # check existing
    existing = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered")
    await db.refresh(user)
    return UserResponse.model_validate(user)


@app.delete("/api/links/{code}", status_code=status.HTTP_204_NO_CONTENT, tags=["api"])
async def delete_link(
    code: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(delete(Link).where(Link.code == code))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Short code not found")
    await db.commit()


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
