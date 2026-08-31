from pathlib import Path
import shutil
import zipapp


ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
SOURCE = ROOT / "repoxray.py"
BUILD_DIR = ROOT / ".build"


def main():
    if not SOURCE.exists():
        raise SystemExit("repoxray.py not found")

    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    BUILD_DIR.mkdir()
    shutil.copy2(SOURCE, BUILD_DIR / "__main__.py")

    DIST.mkdir(exist_ok=True)
    output = DIST / "repoxray.pyz"

    if output.exists():
        output.unlink()

    zipapp.create_archive(
        BUILD_DIR,
        target=output,
        interpreter="/usr/bin/env python3",
    )

    shutil.rmtree(BUILD_DIR)

    print(f"Built: {output}")


if __name__ == "__main__":
    main()