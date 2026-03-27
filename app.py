from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from db import get_connection, init_db
from services import (
    build_project,
    clone_repository,
    delete_path,
    sync_repository,
)

app = Flask(__name__)
init_db()


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def build_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def row_to_dict(row):
    return {key: row[key] for key in row.keys()}


def get_project_by_id(project_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return row_to_dict(row) if row else None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/projects", methods=["GET"])
def list_projects():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY id DESC").fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/api/projects", methods=["POST"])
def create_project():
    payload = request.get_json(silent=True) or {}
    required = [
        "name",
        "repo_url",
        "git_username",
        "git_token",
        "local_base_path",
        "build_script",
    ]
    missing = [k for k in required if not str(payload.get(k, "")).strip()]
    if missing:
        return jsonify({"ok": False, "message": f"Missing required fields: {', '.join(missing)}"}), 400

    created_at = now_text()

    with get_connection() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO projects
                (name, repo_url, git_username, git_token, local_base_path, repo_local_path, build_script, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["name"].strip(),
                    payload["repo_url"].strip(),
                    payload["git_username"].strip(),
                    payload["git_token"].strip(),
                    payload["local_base_path"].strip(),
                    "",
                    payload["build_script"],
                    created_at,
                    created_at,
                ),
            )
            project_id = cursor.lastrowid
        except Exception as exc:
            return jsonify({"ok": False, "message": f"Create project failed: {exc}"}), 400

        safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in payload["name"]).strip("_") or "project"
        repo_local_path = str(Path(payload["local_base_path"]).expanduser() / f"{safe_name}_{project_id}")

        conn.execute(
            "UPDATE projects SET repo_local_path = ?, updated_at = ? WHERE id = ?",
            (repo_local_path, now_text(), project_id),
        )

    project = get_project_by_id(project_id)
    ok, output = clone_repository(
        project["repo_url"],
        project["git_username"],
        project["git_token"],
        project["repo_local_path"],
    )

    if not ok:
        with get_connection() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        delete_path(project["repo_local_path"])
        return jsonify({"ok": False, "message": "Clone failed", "output": output}), 400

    return jsonify({"ok": True, "message": "Project created and cloned", "output": output})


@app.route("/api/projects/<int:project_id>/credentials", methods=["PUT"])
def update_project_credentials(project_id: int):
    payload = request.get_json(silent=True) or {}
    fields = ["repo_url", "git_username", "git_token", "build_script"]
    missing = [f for f in fields if not str(payload.get(f, "")).strip()]
    if missing:
        return jsonify({"ok": False, "message": f"Missing fields: {', '.join(missing)}"}), 400

    with get_connection() as conn:
        result = conn.execute(
            """
            UPDATE projects
            SET repo_url = ?, git_username = ?, git_token = ?, build_script = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload["repo_url"].strip(),
                payload["git_username"].strip(),
                payload["git_token"].strip(),
                payload["build_script"],
                now_text(),
                project_id,
            ),
        )
        if result.rowcount == 0:
            return jsonify({"ok": False, "message": "Project not found"}), 404

    return jsonify({"ok": True, "message": "Project config updated"})


@app.route("/api/projects/<int:project_id>", methods=["DELETE"])
def delete_project(project_id: int):
    project = get_project_by_id(project_id)
    if not project:
        return jsonify({"ok": False, "message": "Project not found"}), 404

    with get_connection() as conn:
        history_rows = conn.execute(
            "SELECT id, output_dir FROM build_history WHERE project_id = ?",
            (project_id,),
        ).fetchall()

        for row in history_rows:
            delete_path(row["output_dir"])

        conn.execute("DELETE FROM build_history WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    delete_path(project["repo_local_path"])
    return jsonify({"ok": True, "message": "Project and related data deleted"})


@app.route("/api/projects/<int:project_id>/sync", methods=["POST"])
def sync_project(project_id: int):
    project = get_project_by_id(project_id)
    if not project:
        return jsonify({"ok": False, "message": "Project not found"}), 404

    ok, output = sync_repository(project)
    return jsonify({"ok": ok, "output": output, "message": "Sync success" if ok else "Sync failed"})


@app.route("/api/projects/<int:project_id>/build", methods=["POST"])
def project_build(project_id: int):
    project = get_project_by_id(project_id)
    if not project:
        return jsonify({"ok": False, "message": "Project not found"}), 404

    run_id = build_run_id()
    ok, output_dir, output = build_project(project, run_id)

    return jsonify(
        {
            "ok": ok,
            "message": "Build success" if ok else "Build failed",
            "output": output,
            "output_dir": output_dir,
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
