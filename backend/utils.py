from pathlib import Path
from urllib.parse import unquote


def resolve_file_theme(path: str, themes: list):
    """Find which theme a file belongs to.

    Match by: 1) exact theme_file match, 2) file directory matches theme_file dir,
    3) path contains theme slug. Returns first match or None.
    """
    clean_path = unquote(path)
    for t in themes:
        if t.theme_file == clean_path:
            return t
    file_dir = Path(clean_path).parts[0] if Path(clean_path).parts else ""
    for t in themes:
        t_dir = Path(t.theme_file).parts[0] if Path(t.theme_file).parts else ""
        if file_dir and t_dir and file_dir == t_dir:
            return t
    for t in themes:
        if t.slug and t.slug.lower() in clean_path.lower():
            return t
    return None


def scan_files(content_dir: str) -> list[str]:
    """Scan content directory and return sorted list of relative file paths."""
    import os
    files = []
    for root, dirs, filenames in os.walk(content_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in filenames:
            if fn.startswith("."):
                continue
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, content_dir).replace("\\", "/")
            parts = rel.split("/")
            if any(p.startswith(".") for p in parts):
                continue
            files.append(rel)
    return sorted(files)
