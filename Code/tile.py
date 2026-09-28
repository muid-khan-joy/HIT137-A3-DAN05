"""Tile: one square piece of the puzzle picture."""
import cv2


class Tile:
    """A single puzzle piece.

    Encapsulation: the original pixels and the orientation state are private.
    The tile only records HOW it has been changed (rotation + flip); the picture
    shown on screen is rebuilt from the original pixels every time.
    """

    def __init__(self, image, home_index):
        self.__original = image          # pixels of this piece in the solved picture
        self.__home_index = home_index   # grid cell where this piece belongs
        self.__rotation = 0              # number of 90 degree clockwise turns (0-3)
        self.__flipped = False           # True if mirrored left <-> right

    @property
    def home_index(self):
        """Index of the grid cell this tile belongs to (read-only)."""
        return self.__home_index

    def rotate(self, quarter_turns=1):
        """Rotate the tile clockwise by 90 degrees x quarter_turns."""
        self.__rotation = (self.__rotation + quarter_turns) % 4

    def flip_horizontal(self):
        """Mirror the tile left <-> right."""
        # Mirroring a rotated tile reverses the direction of its rotation.
        self.__rotation = (-self.__rotation) % 4
        self.__flipped = not self.__flipped

    def flip_vertical(self):
        """Mirror the tile top <-> bottom (= horizontal flip + 180 degree turn)."""
        self.flip_horizontal()
        self.rotate(2)

    def is_upright(self):
        """True when the tile has its original orientation."""
        return self.__rotation == 0 and not self.__flipped

    def reset(self):
        """Undo every rotation and flip."""
        self.__rotation = 0
        self.__flipped = False

    def get_image(self):
        """Return the tile pixels as they currently look on the board."""
        image = self.__original
        if self.__flipped:
            image = cv2.flip(image, 1)
        for _ in range(self.__rotation):
            image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        return image
