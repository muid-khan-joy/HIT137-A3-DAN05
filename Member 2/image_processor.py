"""ImageProcessor: loads a picture, fits it to the grid, cuts it into Tiles
and stitches Tiles back into one image. (Member 2 - Image Processing)

Used by PuzzleGame like this:

    processor = ImageProcessor(grid_size)
    image     = processor.load(path)             # JPG / PNG / BMP -> BGR array
    original  = processor.fit_to_grid(image)     # square, divides evenly
    tiles     = processor.split(original)        # list of Tile objects
    picture   = processor.assemble(board.tiles)  # Tiles -> one image

Why the puzzle image is always square
-------------------------------------
Tiles are rotated by 90 degrees during play. A 90 degree turn swaps a tile's
width and height, so only a square tile still fits its slot afterwards. An
N x N grid of square tiles is itself square. The picture is scaled with its
aspect ratio kept (never stretched) and then cropped or padded to that square.
"""
import base64
import os
from abc import ABC, abstractmethod

import cv2
import numpy as np

from tile import Tile


# ---------------------------------------------------------------------------
# Errors - every message is written so the GUI can show it to the player as-is
# ---------------------------------------------------------------------------
class ImageProcessingError(Exception):
    """Base class for all image processing errors (catch this one in the GUI)."""


class ImageLoadError(ImageProcessingError):
    """The chosen file could not be turned into a usable image."""


class UnsupportedFormatError(ImageLoadError):
    """The file is not a JPG, PNG or BMP."""


class CorruptImageError(ImageLoadError):
    """The file has an image extension but OpenCV cannot decode it."""


class ImageTooSmallError(ImageLoadError):
    """The picture is too small to be cut into the chosen grid."""


class InvalidGridSizeError(ImageProcessingError, ValueError):
    """A grid size other than 3, 4 or 5 was requested."""


# ---------------------------------------------------------------------------
# Fit strategies: two ways of turning any picture into a square
# (inheritance + polymorphism - ImageProcessor just calls strategy.fit())
# ---------------------------------------------------------------------------
class FitStrategy(ABC):
    """Turns an image of any shape into a side x side square without distortion."""

    def fit(self, image, side):
        """Template method: checks the input, lets the subclass do the work,
        then checks the result is exactly side x side."""
        if side <= 0:
            raise ValueError("side must be a positive number of pixels")
        result = self._fit(image, side)
        if result.shape[:2] != (side, side):
            raise ImageProcessingError(f"{type(self).__name__} produced the wrong size")
        return result

    @abstractmethod
    def _fit(self, image, side):
        """Each subclass decides how the square is reached."""

    @staticmethod
    def _resize(image, width, height):
        """Resize using the best interpolation for the direction of scaling.

        INTER_AREA avoids jagged/moire patterns when shrinking big photos,
        INTER_CUBIC keeps edges smooth when enlarging small images.
        """
        old_h, old_w = image.shape[:2]
        shrinking = width * height < old_w * old_h
        method = cv2.INTER_AREA if shrinking else cv2.INTER_CUBIC
        return cv2.resize(image, (width, height), interpolation=method)


class CropToSquare(FitStrategy):
    """Scale so the SHORTER side fills the square, then cut off the overflow
    evenly from both ends. Every tile shows real picture detail (default)."""

    def _fit(self, image, side):
        height, width = image.shape[:2]
        scale = side / min(height, width)
        new_w = max(side, round(width * scale))
        new_h = max(side, round(height * scale))
        resized = self._resize(image, new_w, new_h)
        top = (new_h - side) // 2
        left = (new_w - side) // 2
        return resized[top:top + side, left:left + side].copy()


class PadToSquare(FitStrategy):
    """Scale so the LONGER side fits the square, then add plain borders.
    The whole picture stays visible, but wide images give some blank tiles."""

    def __init__(self, colour=(40, 40, 40)):
        self.__colour = tuple(int(c) for c in colour)   # BGR

    @property
    def colour(self):
        return self.__colour

    def _fit(self, image, side):
        height, width = image.shape[:2]
        scale = side / max(height, width)
        new_w = min(side, max(1, round(width * scale)))
        new_h = min(side, max(1, round(height * scale)))
        resized = self._resize(image, new_w, new_h)
        top = (side - new_h) // 2
        left = (side - new_w) // 2
        return cv2.copyMakeBorder(resized, top, side - new_h - top, left, side - new_w - left,
                                  cv2.BORDER_CONSTANT, value=self.__colour)


# ---------------------------------------------------------------------------
# ImageProcessor
# ---------------------------------------------------------------------------
class ImageProcessor:
    """All OpenCV work for one puzzle: load, fit, split and assemble."""

    SUPPORTED_GRID_SIZES = (3, 4, 5)
    SUPPORTED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp")

    # Pass straight to filedialog.askopenfilename(filetypes=...)
    FILE_DIALOG_TYPES = (
        ("Image files", "*.jpg *.jpeg *.png *.bmp *.JPG *.JPEG *.PNG *.BMP"),
        ("JPEG", "*.jpg *.jpeg"),
        ("PNG", "*.png"),
        ("Bitmap", "*.bmp"),
    )

    DEFAULT_MAX_SIDE = 480        # two 480px images side by side fit a 1366 x 768 laptop
    MIN_PIXELS_PER_TILE = 10      # smaller source images are rejected
    BACKGROUND = (255, 255, 255)  # colour shown behind transparent PNG areas (BGR)

    def __init__(self, grid_size=3, max_side=DEFAULT_MAX_SIDE, fit_strategy=None):
        if grid_size not in self.SUPPORTED_GRID_SIZES:
            raise InvalidGridSizeError(
                f"Grid size must be one of {self.SUPPORTED_GRID_SIZES}, not {grid_size!r}.")
        if max_side < grid_size * self.MIN_PIXELS_PER_TILE:
            raise ValueError("max_side is too small for this grid")
        self.__grid_size = grid_size
        self.__side = (max_side // grid_size) * grid_size   # largest size that divides evenly
        self.__fit_strategy = fit_strategy or CropToSquare()

    # ---------- read-only information ----------
    @property
    def grid_size(self):
        return self.__grid_size

    @property
    def side(self):
        """Width (= height) in pixels of the image returned by fit_to_grid()."""
        return self.__side

    @property
    def tile_size(self):
        return self.__side // self.__grid_size

    @property
    def fit_strategy(self):
        return self.__fit_strategy

    @fit_strategy.setter
    def fit_strategy(self, strategy):
        if not isinstance(strategy, FitStrategy):
            raise TypeError("fit_strategy must be a FitStrategy such as CropToSquare() or PadToSquare()")
        self.__fit_strategy = strategy

    @classmethod
    def is_supported(cls, path):
        return os.path.splitext(str(path))[1].lower() in cls.SUPPORTED_EXTENSIONS

    # ---------- 1. load ----------
    def load(self, path):
        """Read a JPG/PNG/BMP file and return it as an 8-bit, 3-channel BGR image.

        Raises an ImageLoadError subclass with a player-friendly message for:
        no file chosen, missing file, folder, wrong format, empty/damaged file,
        or an image too small for the grid.
        """
        self.__check_path(path)
        image = self.__normalise(self.__decode(path))

        needed = self.__grid_size * self.MIN_PIXELS_PER_TILE
        height, width = image.shape[:2]
        if min(height, width) < needed:
            raise ImageTooSmallError(
                f"The image is only {width} x {height} pixels. A {self.__grid_size} x "
                f"{self.__grid_size} puzzle needs at least {needed} pixels on each side.")
        return image

    def __check_path(self, path):
        if not path:
            raise ImageLoadError("No file was selected.")
        if not os.path.exists(path):
            raise ImageLoadError(f"The file could not be found:\n{path}")
        if os.path.isdir(path):
            raise ImageLoadError("Please choose an image file, not a folder.")
        if not self.is_supported(path):
            ext = os.path.splitext(path)[1] or "(no extension)"
            raise UnsupportedFormatError(
                f"'{ext}' files are not supported. Please choose a JPG, PNG or BMP image.")
        if os.path.getsize(path) == 0:
            raise CorruptImageError("The selected file is empty.")

    @staticmethod
    def __decode(path):
        # cv2.imread() fails on Windows paths with non-English characters, so the
        # bytes are read with NumPy and decoded from memory instead.
        try:
            data = np.fromfile(path, dtype=np.uint8)
        except OSError as error:
            raise ImageLoadError(f"The file could not be read: {error.strerror or error}") from error

        # JPEG: IMREAD_COLOR applies the EXIF rotation so phone photos are the right way up.
        # PNG/BMP: IMREAD_UNCHANGED keeps transparency and 16-bit depth for __normalise.
        is_jpeg = path.lower().endswith((".jpg", ".jpeg"))
        image = cv2.imdecode(data, cv2.IMREAD_COLOR if is_jpeg else cv2.IMREAD_UNCHANGED)
        if image is None or image.size == 0:
            raise CorruptImageError("The file could not be opened as an image. It may be "
                                    "damaged, or not really a JPG/PNG/BMP file.")
        return image

    def __normalise(self, image):
        """Any bit depth / channel count -> 8-bit BGR."""
        if image.dtype == np.uint16:                        # 16-bit PNG
            image = (image / 257.0).round().astype(np.uint8)
        elif image.dtype != np.uint8:
            image = cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        if image.ndim == 2:                                 # grayscale
            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        if image.shape[2] == 1:
            return cv2.cvtColor(image[:, :, 0], cv2.COLOR_GRAY2BGR)
        if image.shape[2] == 4:                             # transparency -> blend onto background
            colour = image[:, :, :3].astype(np.float32)
            alpha = image[:, :, 3:4].astype(np.float32) / 255.0
            background = np.array(self.BACKGROUND, dtype=np.float32)
            return (colour * alpha + background * (1.0 - alpha)).round().astype(np.uint8)
        return image[:, :, :3].copy()

    # ---------- 2. resize + crop/pad ----------
    def fit_to_grid(self, image):
        """Scale (keeping aspect ratio) and crop/pad to a side x side square
        that divides evenly into grid_size x grid_size tiles."""
        return self.__fit_strategy.fit(image, self.__side)

    # ---------- 3. split ----------
    def split(self, image):
        """Cut a fitted image into Tile objects, row by row (index 0 = top-left).

        Each Tile gets its own read-only copy of the pixels, so nothing can
        accidentally paint over the reference picture of a piece.
        """
        height, width = image.shape[:2]
        if height != width or width % self.__grid_size:
            raise ImageProcessingError(
                f"A {width} x {height} image cannot be split into an even "
                f"{self.__grid_size} x {self.__grid_size} grid. Call fit_to_grid() first.")
        size = width // self.__grid_size
        tiles = []
        for row in range(self.__grid_size):
            for col in range(self.__grid_size):
                pixels = image[row * size:(row + 1) * size, col * size:(col + 1) * size].copy()
                pixels.setflags(write=False)
                tiles.append(Tile(pixels, row * self.__grid_size + col))
        return tiles

    # ---------- 4. reassemble ----------
    def assemble(self, tiles):
        """Stitch Tiles (in board position order) back into a single image."""
        if len(tiles) != self.__grid_size ** 2:
            raise ImageProcessingError(f"Expected {self.__grid_size ** 2} tiles, got {len(tiles)}")
        images = [tile.get_image() for tile in tiles]
        n = self.__grid_size
        rows = [np.hstack(images[r * n:(r + 1) * n]) for r in range(n)]
        return np.vstack(rows)

    # ---------- helpers for the GUI ----------
    @staticmethod
    def to_rgb(image):
        """OpenCV uses BGR; Tkinter/Pillow expect RGB."""
        return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    @staticmethod
    def to_tk_png_data(image):
        """Encode a BGR image for tk.PhotoImage(data=...). Tk 8.6 reads PNG itself,
        so no Pillow is needed, and cv2.imencode handles BGR -> RGB."""
        ok, buffer = cv2.imencode(".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 1])
        if not ok:
            raise ImageProcessingError("The image could not be prepared for display.")
        return base64.b64encode(buffer.tobytes()).decode("ascii")
