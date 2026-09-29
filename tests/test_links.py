from httpx import AsyncClient

# ---- public routes (no auth) ----


async def test_root(client: AsyncClient) -> None:
    r = await client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


async def test_health(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_unknown_code_returns_404(client: AsyncClient) -> None:
    r = await client.get("/doesnotexist", follow_redirects=False)
    assert r.status_code == 404


# ---- auth ----


async def test_signup_creates_user(client: AsyncClient) -> None:
    r = await client.post(
        "/api/signup",
        json={"email": "new@example.com", "password": "hunter2hunter2"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "new@example.com"
    assert "password" not in body
    assert "password_hash" not in body


async def test_signup_duplicate_email(client: AsyncClient) -> None:
    payload = {"email": "dup@example.com", "password": "hunter2hunter2"}
    r1 = await client.post("/api/signup", json=payload)
    assert r1.status_code == 201

    r2 = await client.post("/api/signup", json=payload)
    assert r2.status_code == 409


async def test_signup_rejects_short_password(client: AsyncClient) -> None:
    r = await client.post(
        "/api/signup",
        json={"email": "x@example.com", "password": "short"},
    )
    assert r.status_code == 422


async def test_login_wrong_password(client: AsyncClient) -> None:
    await client.post(
        "/api/signup",
        json={"email": "login@example.com", "password": "hunter2hunter2"},
    )
    r = await client.post(
        "/api/login",
        json={"email": "login@example.com", "password": "wrongpassword"},
    )
    assert r.status_code == 401


async def test_me_requires_login(client: AsyncClient) -> None:
    r = await client.get("/api/me")
    assert r.status_code == 401


# ---- authenticated shortening ----


async def test_shorten_requires_login(client: AsyncClient) -> None:
    r = await client.post("/api/shorten", json={"url": "https://example.com"})
    assert r.status_code == 401


async def test_shorten_creates_link(auth_client: AsyncClient) -> None:
    r = await auth_client.post("/api/shorten", json={"url": "https://example.com"})
    assert r.status_code == 200
    body = r.json()
    assert body["url"] == "https://example.com/"
    assert len(body["code"]) == 7
    assert body["clicks"] == 0
    assert body["short_url"].endswith(body["code"])


async def test_shorten_rejects_bad_url(auth_client: AsyncClient) -> None:
    r = await auth_client.post("/api/shorten", json={"url": "not-a-url"})
    assert r.status_code == 422


async def test_shorten_requires_url(auth_client: AsyncClient) -> None:
    r = await auth_client.post("/api/shorten", json={})
    assert r.status_code == 422


async def test_redirect_increments_clicks(auth_client: AsyncClient) -> None:
    create = await auth_client.post("/api/shorten", json={"url": "https://example.com"})
    code = create.json()["code"]

    r = await auth_client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "https://example.com/"

    r = await auth_client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 302

    listing = await auth_client.get("/api/links")
    links = {link["code"]: link for link in listing.json()}
    assert links[code]["clicks"] == 2


async def test_list_links_newest_first(auth_client: AsyncClient) -> None:
    codes = []
    for i in range(3):
        r = await auth_client.post("/api/shorten", json={"url": f"https://example.com/{i}"})
        codes.append(r.json()["code"])

    listing = await auth_client.get("/api/links")
    returned = [link["code"] for link in listing.json()]
    assert returned == list(reversed(codes))


async def test_list_links_requires_login(client: AsyncClient) -> None:
    r = await client.get("/api/links")
    assert r.status_code == 401


async def test_delete_link(auth_client: AsyncClient) -> None:
    r = await auth_client.post("/api/shorten", json={"url": "https://example.com"})
    code = r.json()["code"]
    # 200 (not 204) because htmx does not swap on 204 responses;
    # the delete button depends on receiving a 200 with an empty body.
    r = await auth_client.delete(f"/api/links/{code}")
    assert r.status_code == 200

    r = await auth_client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 404


async def test_delete_unknown_returns_404(auth_client: AsyncClient) -> None:
    r = await auth_client.delete("/api/links/doesnotexist")
    assert r.status_code == 404


async def test_users_cannot_delete_each_others_links(
    client: AsyncClient,
) -> None:
    # user A signs up + creates a link
    await client.post(
        "/api/signup",
        json={"email": "a@example.com", "password": "hunter2hunter2"},
    )
    await client.post(
        "/api/login",
        json={"email": "a@example.com", "password": "hunter2hunter2"},
    )
    r = await client.post("/api/shorten", json={"url": "https://only-a.example.com"})
    code = r.json()["code"]

    # user B logs in on a fresh client
    from httpx import ASGITransport
    from httpx import AsyncClient as _AC

    from app.main import app

    async with _AC(transport=ASGITransport(app=app), base_url="http://test") as client_b:
        await client_b.post(
            "/api/signup",
            json={"email": "b@example.com", "password": "hunter2hunter2"},
        )
        await client_b.post(
            "/api/login",
            json={"email": "b@example.com", "password": "hunter2hunter2"},
        )

        # B tries to delete A's link — must 404
        r = await client_b.delete(f"/api/links/{code}")
        assert r.status_code == 404


async def test_users_cannot_see_each_others_links(client: AsyncClient) -> None:
    # A creates a link
    await client.post(
        "/api/signup",
        json={"email": "seer-a@example.com", "password": "hunter2hunter2"},
    )
    await client.post(
        "/api/login",
        json={"email": "seer-a@example.com", "password": "hunter2hunter2"},
    )
    await client.post("/api/shorten", json={"url": "https://a-private.example.com"})

    # B on fresh client
    from httpx import ASGITransport
    from httpx import AsyncClient as _AC

    from app.main import app

    async with _AC(transport=ASGITransport(app=app), base_url="http://test") as client_b:
        await client_b.post(
            "/api/signup",
            json={"email": "seer-b@example.com", "password": "hunter2hunter2"},
        )
        await client_b.post(
            "/api/login",
            json={"email": "seer-b@example.com", "password": "hunter2hunter2"},
        )

        r = await client_b.get("/api/links")
        assert r.json() == []


async def test_custom_alias(auth_client: AsyncClient) -> None:
    r = await auth_client.post(
        "/api/shorten",
        json={"url": "https://example.com", "alias": "my-docs"},
    )
    assert r.status_code == 200
    assert r.json()["code"] == "my-docs"


async def test_alias_conflict_returns_409(auth_client: AsyncClient) -> None:
    payload = {"url": "https://example.com", "alias": "taken-code"}
    r1 = await auth_client.post("/api/shorten", json=payload)
    assert r1.status_code == 200

    r2 = await auth_client.post("/api/shorten", json=payload)
    assert r2.status_code == 409
    assert "taken" in r2.json()["detail"].lower()


async def test_invalid_alias_returns_422(auth_client: AsyncClient) -> None:
    r = await auth_client.post(
        "/api/shorten",
        json={"url": "https://example.com", "alias": "BAD!"},
    )
    assert r.status_code == 422


async def test_empty_alias_generates_random(auth_client: AsyncClient) -> None:
    r = await auth_client.post(
        "/api/shorten",
        json={"url": "https://example.com", "alias": ""},
    )
    assert r.status_code == 200
    assert len(r.json()["code"]) == 7  # random default length
