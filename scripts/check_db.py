import asyncio

import psycopg


async def main() -> None:
    conn = await psycopg.AsyncConnection.connect(
        "postgresql://shortener:shortener@localhost:5432/shortener"
    )
    async with conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT version()")
            row = await cur.fetchone()
            print(row)


if __name__ == "__main__":
    asyncio.run(main())
