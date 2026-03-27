import locale
import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, urlsplit, urlunsplit


def _decode_output(raw: bytes | None) -> str:
    if not raw:
        return ""

    preferred = locale.getpreferredencoding(False) or "utf-8"
    candidates = [preferred, "utf-8", "gb18030", "gbk"]
    for enc in candidates:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue

    return raw.decode("utf-8", errors="replace")


def run_command(args: Iterable[str], cwd: str | None = None) -> tuple[int, str]:
    process = subprocess.run(
        list(args),
        cwd=cwd,
        capture_output=True,
        text=False,
    )
    output = _decode_output(process.stdout) + _decode_output(process.stderr)
    return process.returncode, output


def create_auth_url(repo_url: str, username: str, token: str) -> str:
    parts = urlsplit(repo_url)
    if parts.scheme not in {"http", "https"}:
        return repo_url
    auth = f"{quote(username, safe='')}:{quote(token, safe='')}"
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    netloc = f"{auth}@{host}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def clone_repository(
    repo_url: str,
    username: str,
    token: str,
    target_dir: str,
) -> tuple[bool, str]:
    Path(target_dir).parent.mkdir(parents=True, exist_ok=True)
    code, output = run_command(
        ["git", "clone", create_auth_url(repo_url, username, token), target_dir]
    )
    return code == 0, output


def sync_repository(project: dict) -> tuple[bool, str]:
    repo_dir = project["repo_local_path"]
    if not Path(repo_dir).exists():
        return False, f"Repository not found: {repo_dir}"

    auth_url = create_auth_url(project["repo_url"], project["git_username"], project["git_token"])
    code_set, out_set = run_command(["git", "-C", repo_dir, "remote", "set-url", "origin", auth_url])
    if code_set != 0:
        return False, out_set

    code_pull, out_pull = run_command(["git", "-C", repo_dir, "pull", "--rebase"])
    run_command(["git", "-C", repo_dir, "remote", "set-url", "origin", project["repo_url"]])
    return code_pull == 0, out_set + out_pull


def get_diff_files(project: dict) -> tuple[bool, list[str], str]:
    repo_dir = project["repo_local_path"]
    if not Path(repo_dir).exists():
        return False, [], f"Repository not found: {repo_dir}"

    code, output = run_command(["git", "-C", repo_dir, "status", "--porcelain"])
    if code != 0:
        return False, [], output

    files = []
    for line in output.splitlines():
        if len(line) >= 4:
            files.append(line[3:])
    return True, files, output


def commit_and_push(project: dict, message: str) -> tuple[bool, str]:
    repo_dir = project["repo_local_path"]
    if not Path(repo_dir).exists():
        return False, f"Repository not found: {repo_dir}"

    result_log = []
    code_add, out_add = run_command(["git", "-C", repo_dir, "add", "-A"])
    result_log.append(out_add)
    if code_add != 0:
        return False, "".join(result_log)

    code_check, out_check = run_command(["git", "-C", repo_dir, "status", "--porcelain"])
    result_log.append(out_check)
    if code_check != 0:
        return False, "".join(result_log)
    if not out_check.strip():
        return False, "No local changes to commit."

    code_commit, out_commit = run_command(["git", "-C", repo_dir, "commit", "-m", message])
    result_log.append(out_commit)
    if code_commit != 0:
        return False, "".join(result_log)

    auth_url = create_auth_url(project["repo_url"], project["git_username"], project["git_token"])
    code_set, out_set = run_command(["git", "-C", repo_dir, "remote", "set-url", "origin", auth_url])
    result_log.append(out_set)
    if code_set != 0:
        return False, "".join(result_log)

    code_push, out_push = run_command(["git", "-C", repo_dir, "push", "origin", "HEAD"])
    result_log.append(out_push)
    run_command(["git", "-C", repo_dir, "remote", "set-url", "origin", project["repo_url"]])
    return code_push == 0, "".join(result_log)


def _safe_build_folder_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name).strip("_") or "project"


def _build_script_command(script: str) -> list[str]:
    if os.name == "nt":
        shell_bin = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
        return [shell_bin, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]

    if Path("/bin/bash").exists():
        return ["/bin/bash", "-lc", script]

    return ["/bin/sh", "-c", script]


def build_project(project: dict, build_id: str) -> tuple[bool, str, str]:
    repo_dir = Path(project["repo_local_path"])
    if not repo_dir.exists():
        return False, "", f"Repository not found: {repo_dir}"

    script = str(project.get("build_script", "")).strip()
    if not script:
        return False, "", "Build script is empty."

    command = _build_script_command(script)
    code_build, output = run_command(command, cwd=str(repo_dir))

    history_root = repo_dir / ".auto_build_history"
    history_root.mkdir(parents=True, exist_ok=True)

    folder_name = f"{_safe_build_folder_name(project['name'])}_{build_id}"
    isolated_output_dir = history_root / folder_name
    if isolated_output_dir.exists():
        shutil.rmtree(isolated_output_dir)
    isolated_output_dir.mkdir(parents=True, exist_ok=True)

    artifacts_dir = isolated_output_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    copied_any = False
    for candidate in ["target", "dist", "build"]:
        src = repo_dir / candidate
        if src.exists() and src.is_dir():
            shutil.copytree(src, artifacts_dir / candidate)
            copied_any = True

    log_file = isolated_output_dir / "build.log"
    log_file.write_text(output, encoding="utf-8", errors="replace")

    if not copied_any:
        output += "\nNo known artifact folder found (target/dist/build). Only build.log was saved."

    if code_build != 0:
        return False, str(isolated_output_dir), output

    return True, str(isolated_output_dir), output


def delete_path(path_text: str) -> None:
    path = Path(path_text)
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
