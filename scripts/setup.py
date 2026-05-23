"""
EIDOLON OS — Setup & dependency check script.
Run: python scripts/setup.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_python_version():
    major, minor = sys.version_info[:2]
    print(f"Python {major}.{minor}", end="")
    if (major, minor) >= (3, 11):
        print(" ✓")
    else:
        print(" ✗ — requires Python 3.11+")
        sys.exit(1)


def install_deps():
    req = ROOT / "requirements.txt"
    print(f"\nInstalling from {req} ...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req)],
        capture_output=False,
    )
    if result.returncode != 0:
        print("\n[WARN] Some packages failed. Check errors above.")
        print("If chromadb fails on Python 3.14, create a 3.12 venv:")
        print("  py -3.12 -m venv .venv && .venv\\Scripts\\activate")
    else:
        print("\nAll packages installed.")


def verify_imports():
    failures = []
    checks = [
        ("fastapi", "FastAPI"),
        ("chromadb", "ChromaDB"),
        ("sentence_transformers", "sentence-transformers"),
        ("easyocr", "EasyOCR"),
        ("mss", "mss"),
        ("PIL", "Pillow"),
        ("cv2", "OpenCV"),
        ("sqlalchemy", "SQLAlchemy"),
        ("tiktoken", "tiktoken"),
    ]
    print("\nVerifying imports:")
    for module, name in checks:
        try:
            __import__(module)
            print(f"  {name:30s} ✓")
        except ImportError as e:
            print(f"  {name:30s} ✗  ({e})")
            failures.append(name)

    if failures:
        print(f"\n[FAIL] Missing: {', '.join(failures)}")
    else:
        print("\nAll core imports OK. Ready to launch.")


if __name__ == "__main__":
    print("=== EIDOLON OS Setup ===\n")
    check_python_version()
    install_deps()
    verify_imports()
