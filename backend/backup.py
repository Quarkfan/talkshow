"""Async SQLite backup to GitHub with debounce."""
import os
import shutil
import subprocess
import time
from pathlib import Path
from threading import Lock, Thread

BACKUP_DIR = Path("/tmp/talkshow-backup")
DB_SRC = Path("/app/data/talkshow.db")
BACKUP_FILE = BACKUP_DIR / "backups" / "talkshow.db"
PREV_FILE = BACKUP_DIR / "backups" / "talkshow.db.prev"
GIT_REPO = BACKUP_DIR / ".git"

_ssh_cmd = "ssh -i /root/.ssh/id_ed25519_github -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/root/.ssh/known_hosts"

_lock = Lock()
_last_backup_time = 0
_cooldown = 30  # seconds


def _git_env():
    env = os.environ.copy()
    env["GIT_SSH_COMMAND"] = _ssh_cmd
    return env


def _git(*args):
    """Run git command in backup repo directory."""
    return subprocess.run(
        ["git", "-C", str(BACKUP_DIR)] + list(args),
        capture_output=True, timeout=60, env=_git_env()
    )


_ready = False


def _run_backup():
    """Execute backup: copy DB → commit → force push. Non-blocking."""
    if not _ready:
        print("[backup] skipped — not initialized yet")
        return
    global _last_backup_time
    try:
        # Ensure backups dir exists
        (BACKUP_DIR / "backups").mkdir(parents=True, exist_ok=True)

        # Preserve previous backup before overwriting
        if BACKUP_FILE.exists():
            shutil.copy2(str(BACKUP_FILE), str(PREV_FILE))

        # Copy current database
        shutil.copy2(str(DB_SRC), str(BACKUP_FILE))

        # Git add, commit (--amend to overwrite history), force push
        _git("add", "backups/talkshow.db")
        _git("commit", "--amend", "--no-edit", "-m", "db backup")
        _git("push", "--force", "origin", "main")
        print("[backup] OK —", time.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:
        print(f"[backup] FAILED: {e}")


def _backup_thread():
    """Debounce wrapper: only run if cooldown has passed."""
    global _last_backup_time
    with _lock:
        now = time.time()
        if now - _last_backup_time < _cooldown:
            return  # still in cooldown
        _last_backup_time = now
    t = Thread(target=_run_backup, daemon=True)
    t.start()


def schedule_backup():
    """Call this after any non-log mutation. Safe to call from request handlers."""
    Thread(target=_backup_thread, daemon=True).start()


def init_backup_repo():
    """Clone or reset the backup repo on startup. Configure git identity."""
    try:
        if GIT_REPO.exists():
            # Repo exists, just pull
            _git("pull", "origin", "main")
        else:
            # First time: clone
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["git", "clone", "git@github.com:Quarkfan/talkshow.git", str(BACKUP_DIR)],
                capture_output=True, timeout=60, env=_git_env()
            )
            if result.returncode != 0:
                print(f"[backup] Clone failed: {result.stderr.decode()}")
                return

        # Configure git identity for this repo
        _git("config", "user.email", "talkshow@quarkfan.com")
        _git("config", "user.name", "talkshow")

        # Ensure backups dir and initial commit
        backups_dir = BACKUP_DIR / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        (backups_dir / ".gitkeep").touch()

        # Check if we already have a commit for .gitkeep
        status = _git("status", "--porcelain", "backups/.gitkeep")
        if status.stdout.decode().strip():
            _git("add", "backups/.gitkeep")
            _git("commit", "-m", "init backup dir")
            _git("push", "-u", "origin", "main")

        print("[backup] Repo initialized")
        global _ready
        _ready = True
    except Exception as e:
        print(f"[backup] Init failed: {e}")
