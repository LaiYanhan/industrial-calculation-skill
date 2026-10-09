"""Create a portable source delivery, excluding environments and runtime data."""

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORIES = ("engine", "scenarios", "integrations", "tests", "docs")
ROOT_FILES = ("README.md", "design.md", "skill_api.py", "requirements.txt", ".gitignore")
SOURCE_SUFFIXES = frozenset((".py", ".json", ".yaml", ".yml", ".xlsx", ".md", ".txt"))
EXCLUDED_PARTS = frozenset(("__pycache__", ".git", ".venv", "venv", "env", ".pytest_cache"))


def source_files(root: Path) -> list[Path]:
    candidates = [root / name for name in ROOT_FILES]
    candidates.append(root / "subagent_workspace" / "ci_runner.py")
    for directory in SOURCE_DIRECTORIES:
        for path in (root / directory).rglob("*"):
            relative = path.relative_to(root)
            if any(part in EXCLUDED_PARTS or part.startswith(".") for part in relative.parts):
                continue
            if path.suffix.lower() in SOURCE_SUFFIXES or path.name in ("LICENSE", "NOTICE", "VERSION"):
                candidates.append(path)
    return sorted(path for path in candidates if path.is_file() and not path.is_symlink())


def build_package(destination: Path | None = None, *, root: Path = PROJECT_ROOT) -> Path:
    output = destination or root / "exports" / "industrial-calculation-tools.zip"
    output = output.absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path in source_files(root):
            archive.write(path, path.relative_to(root).as_posix())
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="默认输出到 exports/industrial-calculation-tools.zip")
    args = parser.parse_args(argv)
    print(build_package(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
