"""Small integration checks that do not require opening the Tkinter window."""

from pathlib import Path
import sys

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for folder in ("Member 1", "Member 2", "Member 3"):
    sys.path.insert(0, str(ROOT / folder))

from game import PuzzleGame
from image_processor import ImageProcessor
from puzzle_board import PuzzleBoard
from transformations import (
    FlipTransformation,
    RotateTransformation,
    Scrambler,
    SwapTransformation,
)


def build_sample(path: Path) -> None:
    image = np.zeros((600, 800, 3), dtype=np.uint8)
    block = 50
    for row in range(12):
        for col in range(16):
            image[
                row * block:(row + 1) * block,
                col * block:(col + 1) * block,
            ] = (
                (30 + col * 11) % 255,
                (50 + row * 17) % 255,
                (80 + (row + col) * 13) % 255,
            )
    if not cv2.imwrite(str(path), image):
        raise RuntimeError("Could not create test image")


def test_scrambler_rules() -> None:
    for grid_size, expected_count in ((3, 6), (4, 12), (5, 20)):
        processor = ImageProcessor(grid_size)
        side = processor.side
        image = np.zeros((side, side, 3), dtype=np.uint8)
        for index in range(grid_size * grid_size):
            row, col = divmod(index, grid_size)
            tile = processor.tile_size
            image[row * tile:(row + 1) * tile, col * tile:(col + 1) * tile] = (
                (index * 29) % 255,
                (index * 53) % 255,
                (index * 83) % 255,
            )

        board = PuzzleBoard(processor.split(image), grid_size)
        plan = Scrambler(grid_size, seed=12345).generate(board)

        assert len(plan) == expected_count
        assert any(isinstance(item, SwapTransformation) for item in plan)
        assert any(isinstance(item, RotateTransformation) for item in plan)
        assert any(isinstance(item, FlipTransformation) for item in plan)

        targets = [position for item in plan for position in item.targets]
        assert len(targets) == len(set(targets)), "A tile target was reused"


def test_full_game_flow(sample_path: Path) -> None:
    for grid_size in (3, 4, 5):
        game = PuzzleGame(str(sample_path), grid_size)

        assert game.grid_size == grid_size
        assert game.moves == 0
        assert game.hints_left == 3
        assert game.incorrect_count() > 0
        assert not game.finished

        assert game.use_hint() is True
        assert game.hint is not None
        assert game.hints_left == 2

        # Selection must always be cleared after a real rotate or flip move.
        # This prevents an invisible stale selection from swapping on the next click.
        game.select(0)
        assert game.selected == 0
        game.rotate(0)
        assert game.moves == 1
        assert game.hint is None
        assert game.selected is None

        moves_before = game.moves
        game.select(1)
        assert game.selected == 1
        assert game.moves == moves_before

        game.flip(1)
        assert game.moves == moves_before + 1
        assert game.selected is None

        game.solve()
        assert game.finished
        assert game.moves == 0
        assert game.incorrect_count() == 0


def main() -> None:
    sample = ROOT / "tests" / "_sample_test_image.png"
    build_sample(sample)
    try:
        test_scrambler_rules()
        test_full_game_flow(sample)
    finally:
        sample.unlink(missing_ok=True)
    print("All core integration checks passed for 3x3, 4x4 and 5x5.")


if __name__ == "__main__":
    main()
