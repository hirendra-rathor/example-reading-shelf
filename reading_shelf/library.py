"""Keep the reader's articles in the local SQLite library.

The library store owns the rules for what an article may contain and is the only
code that reads or writes the ``articles`` table.
"""

import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA_VERSION = 1

STATUSES = ("to_read", "reading", "read")
DEFAULT_STATUS = "to_read"

MAX_URL_LENGTH = 2048
MAX_TITLE_LENGTH = 300
MAX_NOTE_LENGTH = 10_000

ARTICLES_TABLE = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'to_read'
        CHECK (status IN ('to_read', 'reading', 'read')),
    saved_at TEXT NOT NULL
)
"""


class LibraryError(Exception):
    """A request the library refuses. The message is safe to show the reader."""


class InvalidInput(LibraryError):
    """The request breaks one of the library's rules."""


class NotFound(LibraryError):
    """The requested article is not in the library."""


class DuplicateLink(LibraryError):
    """The link is already saved; ``article`` is the existing article."""

    def __init__(self, article: dict):
        super().__init__("That link is already in your library.")
        self.article = article


def connect(path: str | Path) -> sqlite3.Connection:
    """Open the library file. Transactions are explicit (see ``transaction``)."""
    connection = sqlite3.connect(path, isolation_level=None)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def transaction(connection: sqlite3.Connection):
    """Commit every statement in the block together, or none of them."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
    except BaseException:
        connection.execute("ROLLBACK")
        raise
    connection.execute("COMMIT")


def initialize(path: str | Path) -> None:
    """Create the library schema if it is missing; keep any existing data."""
    with closing(connect(path)) as connection:
        # Reading the version first makes an unreadable file fail at startup.
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        with transaction(connection):
            connection.execute(ARTICLES_TABLE)
            if version < SCHEMA_VERSION:
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def clean_url(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidInput("Paste the article’s link.")
    url = value.strip()
    if len(url) > MAX_URL_LENGTH:
        raise InvalidInput(f"Links can be at most {MAX_URL_LENGTH} characters.")
    if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in url):
        raise InvalidInput("Links can’t contain spaces or control characters.")
    try:
        parts = urlsplit(url)
    except ValueError:
        raise InvalidInput("That doesn’t look like a web link.") from None
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise InvalidInput("Links must start with http:// or https:// and name a website.")
    return url


def clean_title(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidInput("Give the article a title.")
    title = " ".join(value.split())
    if len(title) > MAX_TITLE_LENGTH:
        raise InvalidInput(f"Titles can be at most {MAX_TITLE_LENGTH} characters.")
    return title


def clean_note(value) -> str:
    if not isinstance(value, str):
        raise InvalidInput("A note must be text.")
    if len(value) > MAX_NOTE_LENGTH:
        raise InvalidInput(f"Notes can be at most {MAX_NOTE_LENGTH} characters.")
    return value


def clean_status(value) -> str:
    if value not in STATUSES:
        raise InvalidInput("Status must be one of: to_read, reading, read.")
    return value


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _article(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "url": row["url"],
        "title": row["title"],
        "note": row["note"],
        "status": row["status"],
        "saved_at": row["saved_at"],
    }


class Library:
    """Article operations on one open library connection."""

    EDITABLE_FIELDS = ("note", "status")

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def list_articles(self) -> list[dict]:
        rows = self.connection.execute(
            "SELECT * FROM articles ORDER BY saved_at DESC, id DESC"
        ).fetchall()
        return [_article(row) for row in rows]

    def get_article(self, article_id: int) -> dict:
        row = self.connection.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
        if row is None:
            raise NotFound("That article isn’t in your library.")
        return _article(row)

    def find_by_url(self, url: str) -> dict | None:
        row = self.connection.execute("SELECT * FROM articles WHERE url = ?", (url,)).fetchone()
        return _article(row) if row else None

    def add_article(self, url, title) -> dict:
        url = clean_url(url)
        title = clean_title(title)
        try:
            with transaction(self.connection):
                existing = self.find_by_url(url)
                if existing:
                    raise DuplicateLink(existing)
                cursor = self.connection.execute(
                    "INSERT INTO articles (url, title, note, status, saved_at) VALUES (?, ?, '', ?, ?)",
                    (url, title, DEFAULT_STATUS, _now()),
                )
        except sqlite3.IntegrityError:
            # Another request saved the same link between our check and insert.
            raise DuplicateLink(self.find_by_url(url)) from None
        return self.get_article(cursor.lastrowid)

    def update_article(self, article_id: int, changes: dict) -> dict:
        unknown = sorted(set(changes) - set(self.EDITABLE_FIELDS))
        if unknown:
            raise InvalidInput("Only an article’s note and status can be changed.")
        if not changes:
            raise InvalidInput("Send a note or a status to change.")
        values = {}
        if "note" in changes:
            values["note"] = clean_note(changes["note"])
        if "status" in changes:
            values["status"] = clean_status(changes["status"])
        assignments = ", ".join(f"{field} = ?" for field in values)
        with transaction(self.connection):
            cursor = self.connection.execute(
                f"UPDATE articles SET {assignments} WHERE id = ?",
                (*values.values(), article_id),
            )
            if cursor.rowcount == 0:
                raise NotFound("That article isn’t in your library.")
        return self.get_article(article_id)
