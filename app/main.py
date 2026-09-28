from pathlib import Path
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.db import get_db
from app.models import Link, User
from app.schemas import LinkResponse, ShortenForm, ShortenRequest, UserCreate, UserResponse
from app.security import hash_password, verify_password
from app.shortcode import generate_code

BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Shortener", version="0.1.0")

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="shortener_session",
    max_age=60 * 60 * 24 * 14,  # 14 days
    same_site="lax",
    https_only=False,  # set True in production
)

# ---------- Helpers ----------


async def _create_link(url: str, owner_id: int, db: AsyncSession) -> Link:
    for _ in range(5):
        link = Link(code=generate_code(), url=url, owner_id=owner_id)
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


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = await db.get(User, user_id)
    if user is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# _links: dict[str, str] = {} added the db so no need for this

# ---------- Routes ----------


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    user_id = request.session.get("user_id")
    user: User | None = None
    links: list[Link] = []

    if user_id is not None:
        user = await db.get(User, user_id)
        if user is None:
            request.session.clear()
        else:
            result = await db.scalars(
                select(Link).where(Link.owner_id == user.id).order_by(Link.id.desc()).limit(50)
            )
            links = list(result.all())

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"links": links, "user": user},
    )


from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"user": None, "error": None},
    )


@app.post("/login", response_class=HTMLResponse)
async def login_form(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    user = await db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"user": None, "error": "Invalid email or password"},
            status_code=401,
        )
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request) -> HTMLResponse:
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(
        request=request,
        name="signup.html",
        context={"user": None, "error": None},
    )


@app.post("/signup", response_class=HTMLResponse)
async def signup_form(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    # basic validation — reuse server-side rules
    email_norm = email.strip().lower()
    if "@" not in email_norm or len(password) < 8:
        return templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={"user": None, "error": "Enter a valid email and a password of 8+ characters"},
            status_code=400,
        )

    existing = await db.scalar(select(User).where(User.email == email_norm))
    if existing is not None:
        return templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={"user": None, "error": "That email is already registered"},
            status_code=409,
        )

    user = User(email=email_norm, password_hash=hash_password(password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={"user": None, "error": "That email is already registered"},
            status_code=409,
        )
    await db.refresh(user)

    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
async def logout_form(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/", status_code=303)


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


# ---------- Auth ----------


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


@app.post("/api/login", tags=["auth"])
async def login(
    request: Request,
    payload: UserCreate,  # reuse: email + password
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        # Same error for "no such user" and "wrong password" — don't leak which.
        raise HTTPException(status_code=401, detail="Invalid email or password")

    request.session["user_id"] = user.id
    return {"message": "logged in", "email": user.email}


@app.post("/api/logout", tags=["auth"])
async def logout(request: Request) -> dict[str, str]:
    request.session.clear()
    return {"message": "logged out"}


@app.get("/api/me", response_model=UserResponse, tags=["auth"])
async def me(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    user = await db.get(User, user_id)
    if user is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Not logged in")
    return UserResponse.model_validate(user)


# ---------- API ----------


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/shorten", response_model=LinkResponse, tags=["api"])
async def shorten(
    payload: ShortenRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LinkResponse:
    link = await _create_link(str(payload.url), user.id, db)
    return LinkResponse(
        code=link.code,
        url=link.url,
        short_url=f"{settings.base_url}/{link.code}",
        clicks=link.clicks,
        created_at=link.created_at,
    )


@app.get("/api/links", response_model=list[LinkResponse], tags=["api"])
async def list_links(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
) -> list[LinkResponse]:
    result = await db.scalars(
        select(Link).where(Link.owner_id == user.id).order_by(Link.id.desc()).limit(limit)
    )
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


@app.delete("/api/links/{code}", status_code=status.HTTP_204_NO_CONTENT, tags=["api"])
async def delete_link(
    code: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(delete(Link).where(Link.code == code).where(Link.owner_id == user.id))
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
