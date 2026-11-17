"""Keep the reader's articles and collections in the local SQLite library.

The library store owns the rules for what an article and a collection may contain
and is the only code that reads or writes the library tables. A collection holds
references to articles, never copies: an article's note and status live on its one
``articles`` row, whichever view it is read or edited from.
"""

import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA_VERSION = 2

STATUSES = ("to_read", "reading", "read")
DEFAULT_STATUS = "to_read"

MAX_URL_LENGTH = 2048
MAX_TITLE_LENGTH = 300
MAX_NOTE_LENGTH = 10_000
MAX_COLLECTION_NAME_LENGTH = 80

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

COLLECTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    name_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
)
"""

MEMBERSHIPS_TABLE = """
CREATE TABLE IF NOT EXISTS collection_articles (
    collection_id INTEGER NOT NULL REFERENCES collections (id) ON DELETE CASCADE,
    article_id INTEGER NOT NULL REFERENCES articles (id) ON DELETE CASCADE,
    added_at TEXT NOT NULL,
    PRIMARY KEY (collection_id, article_id)
)
"""

# Statements that bring a library up to each schema version, applied in order.
MIGRATIONS = {
    1: [ARTICLES_TABLE],
    2: [COLLECTIONS_TABLE, MEMBERSHIPS_TABLE],
}

ARTICLE_COLUMNS = """
    a.id, a.url, a.title, a.note, a.status, a.saved_at,
    (SELECT group_concat(m.collection_id) FROM collection_articles AS m
     WHERE m.article_id = a.id) AS collection_ids
"""


class LibraryError(Exception):
    """A request the library refuses. The message is safe to show the reader."""


class InvalidInput(LibraryError):
    """The request breaks one of the library's rules."""


class NotFound(LibraryError):
    """The requested article or collection is not in the library."""


class DuplicateLink(LibraryError):
    """The link is already saved; ``article`` is the existing article."""

    def __init__(self, article: dict):
        super().__init__("That link is already in your library.")
        self.article = article


class DuplicateCollection(LibraryError):
    """A collection with the same name exists; ``collection`` is that collection."""

    def __init__(self, collection: dict):
        super().__init__(f"You already have a collection called “{collection['name']}”.")
        self.collection = collection


class UnsupportedLibrary(LibraryError):
    """The library file was written by a newer version of Reading Shelf."""


def connect(path: str | Path) -> sqlite3.Connection:
    """Open the library file. Transactions are explicit (see ``transaction``)."""
    connection = sqlite3.connect(path, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
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
    """Create or upgrade the library schema; keep any existing data.

    The upgrade runs in one transaction, so a failure leaves the file at its
    previous version. A file from a newer Reading Shelf is refused unchanged.
    """
    with closing(connect(path)) as connection:
        # Reading the version first makes an unreadable file fail at startup.
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise UnsupportedLibrary(
                f"This library uses schema version {version}, but this Reading Shelf "
                f"understands up to version {SCHEMA_VERSION}."
            )
        with transaction(connection):
            for target in sorted(MIGRATIONS):
                # Re-running CREATE TABLE IF NOT EXISTS keeps a file whose version
                # was set but whose tables are missing usable.
                for statement in MIGRATIONS[target]:
                    connection.execute(statement)
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


def clean_status_filter(value) -> str | None:
    """An optional status filter: absent or empty means every status."""
    if value is None or value == "":
        return None
    if value not in STATUSES:
        raise InvalidInput("Filter by one of: to_read, reading, read.")
    return value


def clean_collection_name(value) -> tuple[str, str]:
    """Return the display name and the key that decides whether two names are the same."""
    if not isinstance(value, str) or not value.strip():
        raise InvalidInput("Give the collection a name.")
    name = " ".join(value.split())
    if len(name) > MAX_COLLECTION_NAME_LENGTH:
        raise InvalidInput(f"Collection names can be at most {MAX_COLLECTION_NAME_LENGTH} characters.")
    return name, name.casefold()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _article(row: sqlite3.Row) -> dict:
    collection_ids = row["collection_ids"]
    return {
        "id": row["id"],
        "url": row["url"],
        "title": row["title"],
        "note": row["note"],
        "status": row["status"],
        "saved_at": row["saved_at"],
        "collection_ids": sorted(int(value) for value in collection_ids.split(",")) if collection_ids else [],
    }


def _collection(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "article_count": row["article_count"],
        "created_at": row["created_at"],
    }


class Library:
    """Article and collection operations on one open library connection."""

    EDITABLE_FIELDS = ("note", "status")

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    # ----------------------------------------------------------- articles

    def list_articles(self, status: str | None = None) -> list[dict]:
        query = f"SELECT {ARTICLE_COLUMNS} FROM articles AS a"
        parameters = []
        if status is not None:
            query += " WHERE a.status = ?"
            parameters.append(status)
        query += " ORDER BY a.saved_at DESC, a.id DESC"
        return [_article(row) for row in self.connection.execute(query, parameters)]

    def get_article(self, article_id: int) -> dict:
        row = self.connection.execute(
            f"SELECT {ARTICLE_COLUMNS} FROM articles AS a WHERE a.id = ?", (article_id,)
        ).fetchone()
        if row is None:
            raise NotFound("That article isn’t in your library.")
        return _article(row)

    def find_by_url(self, url: str) -> dict | None:
        row = self.connection.execute(
            f"SELECT {ARTICLE_COLUMNS} FROM articles AS a WHERE a.url = ?", (url,)
        ).fetchone()
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

    # -------------------------------------------------------- collections

    def list_collections(self) -> list[dict]:
        rows = self.connection.execute(
            """
            SELECT c.id, c.name, c.created_at, COUNT(m.article_id) AS article_count
            FROM collections AS c
            LEFT JOIN collection_articles AS m ON m.collection_id = c.id
            GROUP BY c.id
            ORDER BY c.name_key, c.id
            """
        ).fetchall()
        return [_collection(row) for row in rows]

    def get_collection(self, collection_id: int) -> dict:
        row = self.connection.execute(
            """
            SELECT c.id, c.name, c.created_at,
                   (SELECT COUNT(*) FROM collection_articles AS m WHERE m.collection_id = c.id) AS article_count
            FROM collections AS c WHERE c.id = ?
            """,
            (collection_id,),
        ).fetchone()
        if row is None:
            raise NotFound("That collection doesn’t exist.")
        return _collection(row)

    def _find_collection_by_key(self, name_key: str) -> dict | None:
        row = self.connection.execute("SELECT id FROM collections WHERE name_key = ?", (name_key,)).fetchone()
        return self.get_collection(row["id"]) if row else None

    def create_collection(self, name) -> dict:
        name, name_key = clean_collection_name(name)
        try:
            with transaction(self.connection):
                existing = self._find_collection_by_key(name_key)
                if existing:
                    raise DuplicateCollection(existing)
                cursor = self.connection.execute(
                    "INSERT INTO collections (name, name_key, created_at) VALUES (?, ?, ?)",
                    (name, name_key, _now()),
                )
        except sqlite3.IntegrityError:
            raise DuplicateCollection(self._find_collection_by_key(name_key)) from None
        return self.get_collection(cursor.lastrowid)

    def list_collection_articles(self, collection_id: int, status: str | None = None) -> list[dict]:
        self.get_collection(collection_id)
        query = (
            f"SELECT {ARTICLE_COLUMNS} FROM articles AS a "
            "JOIN collection_articles AS member ON member.article_id = a.id "
            "WHERE member.collection_id = ?"
        )
        parameters = [collection_id]
        if status is not None:
            query += " AND a.status = ?"
            parameters.append(status)
        query += " ORDER BY a.saved_at DESC, a.id DESC"
        return [_article(row) for row in self.connection.execute(query, parameters)]

    def add_to_collection(self, collection_id: int, article_id: int) -> dict:
        """Put an article in a collection. Adding it again changes nothing."""
        with transaction(self.connection):
            self.get_collection(collection_id)
            self.get_article(article_id)
            self.connection.execute(
                "INSERT OR IGNORE INTO collection_articles (collection_id, article_id, added_at) VALUES (?, ?, ?)",
                (collection_id, article_id, _now()),
            )
        return self.get_article(article_id)

    def remove_from_collection(self, collection_id: int, article_id: int) -> dict:
        """Take an article out of one collection only. Removing it again changes nothing."""
        with transaction(self.connection):
            self.get_collection(collection_id)
            self.get_article(article_id)
            self.connection.execute(
                "DELETE FROM collection_articles WHERE collection_id = ? AND article_id = ?",
                (collection_id, article_id),
            )
        return self.get_article(article_id)
