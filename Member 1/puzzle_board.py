"""PuzzleBoard: keeps the tiles in their current positions."""


class PuzzleBoard:
    """List index = current position on the board, value = Tile object."""

    def __init__(self, tiles, grid_size):
        self.__tiles = list(tiles)
        self.__grid_size = grid_size

    @property
    def tiles(self):
        return tuple(self.__tiles)       # read-only copy

    def tile_at(self, pos):
        return self.__tiles[pos]

    def swap_tiles(self, pos_a, pos_b):
        self.__tiles[pos_a], self.__tiles[pos_b] = self.__tiles[pos_b], self.__tiles[pos_a]

    def apply(self, transformation):
        """Works with ANY Transformation child class (polymorphism)."""
        transformation.apply(self)

    def is_tile_correct(self, pos):
        tile = self.__tiles[pos]
        return tile.home_index == pos and tile.is_upright()

    def incorrect_positions(self):
        return [pos for pos in range(len(self.__tiles)) if not self.is_tile_correct(pos)]

    def incorrect_count(self):
        return len(self.incorrect_positions())

    def is_solved(self):
        return self.incorrect_count() == 0

    def solve(self):
        """Undo all remaining transformations: every tile home and upright."""
        self.__tiles.sort(key=lambda tile: tile.home_index)
        for tile in self.__tiles:
            tile.reset()
