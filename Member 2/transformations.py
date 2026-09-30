"""Tile transformations (Swap, Rotate, Flip) and the random Scrambler.
(Member 2 - Image Processing and Scrambling)

Inheritance + polymorphism
--------------------------
Transformation is an abstract base class. Swap, Rotate and Flip each fill in
the same methods their own way:

    apply(board)           change the PuzzleBoard
    inverse()              the transformation that undoes this one
    targets                which board positions it touches
    changes_pixels(board)  would the player actually SEE a difference?
    random(rng, positions) make a random one (used by the Scrambler)

PuzzleBoard.apply(t), the Scrambler and the player's clicks all use these
without checking which subclass they have. Adding a new transformation type
means writing one subclass and adding it to Scrambler.TRANSFORMATION_TYPES.

The same classes are used for scrambling AND for the player's moves:
    left click x2   -> SwapTransformation(a, b)
    right click     -> RotateTransformation(pos, 1)       (90 degrees clockwise)
    Shift + click   -> FlipTransformation(pos, "h")
"""
import random
from abc import ABC, abstractmethod

import cv2
import numpy as np


class Transformation(ABC):
    """One change made to the puzzle board."""

    NAME = "transformation"   # short label, e.g. for a move history
    TILES_NEEDED = 1          # how many different tiles one instance touches

    # Mean pixel difference (0-255 scale) below which a change is treated as
    # invisible, e.g. flipping a plain sky tile. JPEG noise alone is ~1-2.
    VISIBLE_DIFFERENCE = 4.0

    @property
    @abstractmethod
    def targets(self):
        """Tuple of board positions this transformation touches."""

    @abstractmethod
    def apply(self, board):
        """Perform the transformation on a PuzzleBoard."""

    @abstractmethod
    def inverse(self):
        """Return a Transformation that exactly undoes this one."""

    @abstractmethod
    def changes_pixels(self, board):
        """True if applying this to the board would make a visible difference."""

    @classmethod
    @abstractmethod
    def random(cls, rng, positions):
        """Build a random instance that targets exactly `positions`."""

    @classmethod
    def _looks_different(cls, image_a, image_b):
        diff = cv2.absdiff(image_a, image_b)
        return float(np.mean(diff)) >= cls.VISIBLE_DIFFERENCE

    def __repr__(self):
        return f"<{self}>"


class SwapTransformation(Transformation):
    """Two tiles exchange positions."""

    NAME = "swap"
    TILES_NEEDED = 2

    def __init__(self, pos_a, pos_b):
        if pos_a == pos_b:
            raise ValueError("A swap needs two different positions")
        self.__pos_a = pos_a
        self.__pos_b = pos_b

    @property
    def targets(self):
        return (self.__pos_a, self.__pos_b)

    def apply(self, board):
        board.swap_tiles(self.__pos_a, self.__pos_b)

    def inverse(self):
        return SwapTransformation(self.__pos_a, self.__pos_b)     # swapping again undoes it

    def changes_pixels(self, board):
        return self._looks_different(board.tile_at(self.__pos_a).get_image(),
                                     board.tile_at(self.__pos_b).get_image())

    @classmethod
    def random(cls, rng, positions):
        pos_a, pos_b = positions
        return cls(pos_a, pos_b)

    def __str__(self):
        return f"Swap tiles {self.__pos_a} and {self.__pos_b}"


class RotateTransformation(Transformation):
    """One tile turns clockwise by 90, 180 or 270 degrees (1, 2 or 3 quarter turns)."""

    NAME = "rotate"
    TILES_NEEDED = 1

    def __init__(self, pos, quarter_turns=1):
        quarter_turns %= 4
        if quarter_turns == 0:
            raise ValueError("Rotation must be 90, 180 or 270 degrees (1-3 quarter turns)")
        self.__pos = pos
        self.__quarter_turns = quarter_turns

    @property
    def targets(self):
        return (self.__pos,)

    @property
    def quarter_turns(self):
        return self.__quarter_turns

    @property
    def degrees(self):
        return self.__quarter_turns * 90

    def apply(self, board):
        board.tile_at(self.__pos).rotate(self.__quarter_turns)

    def inverse(self):
        return RotateTransformation(self.__pos, 4 - self.__quarter_turns)

    def changes_pixels(self, board):
        image = board.tile_at(self.__pos).get_image()
        rotated = image
        for _ in range(self.__quarter_turns):
            rotated = cv2.rotate(rotated, cv2.ROTATE_90_CLOCKWISE)
        return self._looks_different(image, rotated)

    @classmethod
    def random(cls, rng, positions):
        (pos,) = positions
        return cls(pos, rng.choice((1, 2, 3)))

    def __str__(self):
        return f"Rotate tile {self.__pos} by {self.degrees}°"


class FlipTransformation(Transformation):
    """One tile is mirrored: "h" = left <-> right, "v" = top <-> bottom."""

    NAME = "flip"
    TILES_NEEDED = 1
    AXES = ("h", "v")

    def __init__(self, pos, axis="h"):
        if axis not in self.AXES:
            raise ValueError(f"Flip axis must be 'h' or 'v', not {axis!r}")
        self.__pos = pos
        self.__axis = axis

    @property
    def targets(self):
        return (self.__pos,)

    @property
    def axis(self):
        return self.__axis

    def apply(self, board):
        tile = board.tile_at(self.__pos)
        if self.__axis == "h":
            tile.flip_horizontal()
        else:
            tile.flip_vertical()

    def inverse(self):
        return FlipTransformation(self.__pos, self.__axis)        # flipping again undoes it

    def changes_pixels(self, board):
        image = board.tile_at(self.__pos).get_image()
        return self._looks_different(image, cv2.flip(image, 1 if self.__axis == "h" else 0))

    @classmethod
    def random(cls, rng, positions):
        (pos,) = positions
        return cls(pos, rng.choice(cls.AXES))

    def __str__(self):
        direction = "horizontally" if self.__axis == "h" else "vertically"
        return f"Flip tile {self.__pos} {direction}"


class Scrambler:
    """Plans a random scramble for one image.

    Rules it guarantees on every load:
      * the number of transformations scales with the grid: 3x3 -> 6, 4x4 -> 12, 5x5 -> 20
      * swap, rotate and flip are ALL used at least once; the rest of the mix is random
      * no tile is targeted twice, so one change can never cancel another out
      * all transformations are generated at once, before any are applied
      * if the board is passed in, every change is one the player can actually see

    Why n x (n - 1) always fits: n*n tiles, n*(n-1) transformations of at least
    one tile each, leaves room for up to n two-tile swaps. The planner keeps to that.
    """

    TRANSFORMATION_TYPES = (SwapTransformation, RotateTransformation, FlipTransformation)
    TRANSFORMATION_COUNTS = {3: 6, 4: 12, 5: 20}
    ATTEMPTS = 25   # tries at finding a visible change before accepting any change

    def __init__(self, grid_size, seed=None):
        if grid_size not in self.TRANSFORMATION_COUNTS:
            raise ValueError(f"Grid size must be 3, 4 or 5, not {grid_size!r}")
        self.__grid_size = grid_size
        self.__rng = random.Random(seed)   # a seed makes the scramble repeatable (for testing)

    @property
    def grid_size(self):
        return self.__grid_size

    @property
    def count(self):
        """How many transformations generate() returns for this grid size."""
        return self.TRANSFORMATION_COUNTS[self.__grid_size]

    def generate(self, board=None):
        """Return the full list of random transformations (does not apply them).

        Passing the PuzzleBoard is optional but recommended: it lets the
        scrambler skip changes the player could not see (e.g. flipping a
        plain blue sky tile, or swapping two identical tiles).
        """
        plan = self.__plan_types()
        free = list(range(self.__grid_size ** 2))
        self.__rng.shuffle(free)

        transformations = []
        for kind in plan:
            chosen = self.__pick(kind, free, board)
            for pos in chosen.targets:
                free.remove(pos)          # a tile is never targeted twice
            transformations.append(chosen)
        return transformations

    def __plan_types(self):
        """Decide the type of every transformation, one of each guaranteed."""
        types = self.TRANSFORMATION_TYPES
        tile_count = self.__grid_size ** 2
        plan = list(types)
        used = sum(kind.TILES_NEEDED for kind in plan)
        smallest = min(kind.TILES_NEEDED for kind in types)

        for remaining in range(self.count - len(plan) - 1, -1, -1):
            # A type fits if the transformations still to come can still get a tile each.
            fits = [kind for kind in types
                    if used + kind.TILES_NEEDED + remaining * smallest <= tile_count]
            choice = self.__rng.choice(fits)
            plan.append(choice)
            used += choice.TILES_NEEDED

        self.__rng.shuffle(plan)
        return plan

    def __pick(self, kind, free, board):
        """Choose random untouched tiles, preferring a change the player can see."""
        candidate = None
        for _ in range(self.ATTEMPTS):
            candidate = kind.random(self.__rng, self.__rng.sample(free, kind.TILES_NEEDED))
            if board is None or candidate.changes_pixels(board):
                return candidate
        return candidate   # e.g. a completely plain image: nothing can look different
