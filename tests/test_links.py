from httpx import AsyncClient


async def test_root(client: AsyncClient) -> None:
    r = await client.get("/")
    assert r.status_code == 200
    assert r.json() == {"message": "hello kali"}


async def test_health(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_shorten_creates_link(client: AsyncClient) -> None:
    r = await client.post("/api/shorten", json={"url": "https://example.com"})
    assert r.status_code == 200
    body = r.json()
    assert body["url"] == "https://example.com/"
    assert len(body["code"]) == 7
    assert body["clicks"] == 0
    assert body["short_url"].endswith(body["code"])


async def test_shorten_rejects_bad_url(client: AsyncClient) -> None:
    r = await client.post("/api/shorten", json={"url": "not-a-url"})
    assert r.status_code == 422


async def test_shorten_requires_url(client: AsyncClient) -> None:
    r = await client.post("/api/shorten", json={})
    assert r.status_code == 422


async def test_redirect_increments_clicks(client: AsyncClient) -> None:
    create = await client.post("/api/shorten", json={"url": "https://example.com"})
    code = create.json()["code"]

    r = await client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "https://example.com/"

    r = await client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 302

    listing = await client.get("/api/links")
    links = {link["code"]: link for link in listing.json()}
    assert links[code]["clicks"] == 2


async def test_unknown_code_returns_404(client: AsyncClient) -> None:
    r = await client.get("/doesnotexist", follow_redirects=False)
    assert r.status_code == 404


async def test_list_links_newest_first(client: AsyncClient) -> None:
    codes = []
    for i in range(3):
        r = await client.post("/api/shorten", json={"url": f"https://example.com/{i}"})
        codes.append(r.json()["code"])

    listing = await client.get("/api/links")
    returned = [link["code"] for link in listing.json()]
    assert returned == list(reversed(codes))
