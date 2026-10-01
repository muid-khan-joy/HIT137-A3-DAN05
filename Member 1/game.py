"""PuzzleGame: game rules (moves, selection, hints, completion). No GUI code here."""
import random

from image_processor import ImageProcessor
from puzzle_board import PuzzleBoard
from transformations import (FlipTransformation, RotateTransformation,
                             Scrambler, SwapTransformation)


class PuzzleGame:
    """One round of the puzzle for one loaded image."""

    MAX_HINTS = 3

    def __init__(self, image_path, grid_size):
        self.__processor = ImageProcessor(grid_size)
        image = self.__processor.load(image_path)
        self.__original = self.__processor.fit_to_grid(image)
        self.__grid_size = grid_size
        self.__board = PuzzleBoard(self.__processor.split(self.__original), grid_size)

        # Scramble: all random transformations generated and applied at once.
        for transformation in Scrambler(grid_size).generate(self.__board):
            self.__board.apply(transformation)

        self.__moves = 0
        self.__hints_used = 0
        self.__selected = None      # position of the selected tile (or None)
        self.__hint = None          # (current position, home position) or None
        self.__finished = False

    # ---------- read-only information for the GUI ----------
    @property
    def original_image(self):
        return self.__original

    @property
    def grid_size(self):
        return self.__grid_size

    @property
    def tile_size(self):
        return self.__original.shape[0] // self.__grid_size

    @property
    def moves(self):
        return self.__moves

    @property
    def hints_left(self):
        return self.MAX_HINTS - self.__hints_used

    @property
    def selected(self):
        return self.__selected

    @property
    def hint(self):
        return self.__hint

    @property
    def finished(self):
        return self.__finished

    def incorrect_count(self):
        return self.__board.incorrect_count()

    def is_tile_correct(self, pos):
        return self.__board.is_tile_correct(pos)

    def current_image(self):
        return self.__processor.assemble(self.__board.tiles)

    # ---------- player actions ----------
    def select(self, pos):
        """Left click: select, deselect, or swap with the selected tile."""
        if self.__finished:
            return
        if self.__selected is None:
            self.__selected = pos
        elif self.__selected == pos:
            self.__selected = None
        else:
            first = self.__selected
            self.__selected = None
            self.__make_move(SwapTransformation(first, pos))

    def rotate(self, pos):
        """Right click: rotate 90 degrees clockwise."""
        if not self.__finished:
            self.__make_move(RotateTransformation(pos, 1))

    def flip(self, pos):
        """Shift + left click: flip horizontally."""
        if not self.__finished:
            self.__make_move(FlipTransformation(pos, "h"))

    def use_hint(self):
        """Mark one incorrect tile. Returns False if no hint can be given."""
        wrong = self.__board.incorrect_positions()
        if self.__finished or self.hints_left == 0 or not wrong:
            return False
        pos = random.choice(wrong)
        self.__hint = (pos, self.__board.tile_at(pos).home_index)
        self.__hints_used += 1
        return True

    def solve(self):
        """Solve button: undo everything and clear moves/score."""
        self.__board.solve()
        self.__moves = 0
        self.__selected = None
        self.__hint = None
        self.__finished = True

    def __make_move(self, transformation):
        # Apply the player's action first, then update all state from the new board.
        self.__board.apply(transformation)
        self.__moves += 1

        # Every completed move clears selection. This keeps the logical state
        # consistent with the GUI: if there is no selection border, no tile is
        # still waiting to be swapped on the next left click.
        self.__selected = None
        self.__hint = None                  # hint circles disappear after the next move

        # Completion is checked only after the transformation has been applied.
        if self.__board.is_solved():
            self.__finished = True
