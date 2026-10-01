"""Single entry point for the HIT137 Assignment 3 puzzle application."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent

# The assignment repository keeps each member's work in a separate folder.
# Add those folders to Python's module search path, then run the integrated GUI.
for member_folder in ("Member 1", "Member 2", "Member 3"):
    path = str(PROJECT_ROOT / member_folder)
    if path not in sys.path:
        sys.path.insert(0, path)

from puzzle_gui import PuzzleApplication


def main() -> None:
    app = PuzzleApplication()
    app.run()


if __name__ == "__main__":
    main()
