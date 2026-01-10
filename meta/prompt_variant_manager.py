from pathlib import Path

BASE = Path("agents/prompts")
VAR = BASE / "variants"

def _prompt_slug(prompt_path: str) -> str:
    return Path(prompt_path).stem

def ensure_variants(prompt_path: str):
    slug = _prompt_slug(prompt_path)
    vdir = VAR / slug
    vdir.mkdir(parents=True, exist_ok=True)

    current = Path(prompt_path).read_text()

    for name in ["A.md", "B.md", "champion.md"]:
        p = vdir / name
        if not p.exists():
            p.write_text(current)

def load_variant(prompt_path: str, variant: str) -> str:
    slug = _prompt_slug(prompt_path)
    return (VAR / slug / f"{variant}.md").read_text()

def save_champion(prompt_path: str, text: str):
    slug = _prompt_slug(prompt_path)
    (VAR / slug / "champion.md").write_text(text)
    Path(prompt_path).write_text(text)
