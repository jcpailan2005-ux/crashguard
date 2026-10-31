from pathlib import Path

backend_main = Path("backend/main.py").read_text(encoding="utf-8")
lines = backend_main.splitlines()

print(f"Total lines in backend/main.py: {len(lines)}")
for i, line in enumerate(lines, 1):
    if any(term in line.lower() for term in ["crash_classifier", "classifier", "best.pt"]):
        print(f"Line {i}: {line}")
