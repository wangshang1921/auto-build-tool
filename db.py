import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "build_tool.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _get_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                repo_url TEXT NOT NULL,
                git_username TEXT NOT NULL,
                git_token TEXT NOT NULL,
                local_base_path TEXT NOT NULL,
                repo_local_path TEXT NOT NULL,
                build_script TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        project_columns = _get_columns(conn, "projects")
        if "build_script" not in project_columns or "build_type" in project_columns or "publish_path" in project_columns:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS projects_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    repo_url TEXT NOT NULL,
                    git_username TEXT NOT NULL,
                    git_token TEXT NOT NULL,
                    local_base_path TEXT NOT NULL,
                    repo_local_path TEXT NOT NULL,
                    build_script TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO projects_new
                (id, name, repo_url, git_username, git_token, local_base_path, repo_local_path, build_script, created_at, updated_at)
                SELECT id, name, repo_url, git_username, git_token, local_base_path, repo_local_path, '', created_at, updated_at
                FROM projects
                """
            )
            conn.execute("DROP TABLE projects")
            conn.execute("ALTER TABLE projects_new RENAME TO projects")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS build_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                build_time TEXT NOT NULL,
                status TEXT NOT NULL,
                output_dir TEXT NOT NULL,
                log_text TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
            """
        )

        history_columns = _get_columns(conn, "build_history")
        if "published_to" in history_columns:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS build_history_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    build_time TEXT NOT NULL,
                    status TEXT NOT NULL,
                    output_dir TEXT NOT NULL,
                    log_text TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                INSERT INTO build_history_new
                (id, project_id, build_time, status, output_dir, log_text)
                SELECT id, project_id, build_time, status, output_dir, log_text
                FROM build_history
                """
            )
            conn.execute("DROP TABLE build_history")
            conn.execute("ALTER TABLE build_history_new RENAME TO build_history")
