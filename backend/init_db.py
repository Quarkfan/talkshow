"""Seed the themes table by scanning the talkResources content directory."""
import re
from pathlib import Path
from .database import SessionLocal
from .models import Theme


def extract_title_from_html(filepath: Path) -> str:
    text = filepath.read_text(encoding="utf-8")
    match = re.search(r"<title>(.*?)</title>", text, re.IGNORECASE)
    return match.group(1).strip() if match else filepath.stem


def scan_content_dir(content_dir: Path):
    db = SessionLocal()
    themes_dir = content_dir / "themes"
    if not themes_dir.exists():
        print(f"[init_db] No themes directory at {themes_dir}")
        db.close()
        return

    for html_file in themes_dir.glob("*.html"):
        rel_path = f"themes/{html_file.name}"
        title = extract_title_from_html(html_file)
        slug = html_file.stem.replace(" ", "-").lower()

        existing = db.query(Theme).filter(Theme.slug == slug).first()
        if existing:
            existing.title = title
            existing.theme_file = rel_path
        else:
            theme = Theme(
                slug=slug, title=title, theme_file=rel_path,
                description=f"Theme: {title}", icon="🚀", visible=False
            )
            db.add(theme)

    pres_dir = content_dir / "presentations"
    if pres_dir.exists():
        pres_count = len(list(pres_dir.glob("*.html")))
        first_theme = db.query(Theme).first()
        if first_theme:
            first_theme.presentation_count = pres_count

    db.commit()
    print(f"[init_db] Seeded themes from {themes_dir}")
    db.close()


def init_db(content_dir: Path):
    from .database import engine, Base
    Base.metadata.create_all(bind=engine)
    scan_content_dir(content_dir)
