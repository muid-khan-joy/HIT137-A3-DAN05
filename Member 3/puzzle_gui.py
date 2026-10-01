"""Tkinter interface and integration layer for the HIT137 image puzzle game.

Member 3 - GUI, interaction, feedback, integration and final testing.

The GUI keeps game rules in Member 1's PuzzleGame and image processing in
Member 2's ImageProcessor. This file coordinates those parts and presents the
current game state to the player.
"""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from game import PuzzleGame
from image_processor import ImageProcessingError, ImageProcessor


class PuzzleApplication:
    """Desktop interface for loading, playing and completing image puzzles."""

    WINDOW_BG = "#101722"
    PANEL_BG = "#182333"
    PANEL_ALT = "#202D3F"
    TEXT = "#E9F0F7"
    MUTED = "#A9B6C6"
    ACCENT = "#48C9A9"
    ACCENT_DARK = "#2AA78A"
    WARNING = "#FFB45A"
    BLUE = "#4EA5FF"
    GREEN = "#4BD37B"
    GRID = "#7C8A9B"
    CANVAS_BG = "#0A0F17"
    CONTROL_KEY_BG = "#2A3A4F"

    DIFFICULTIES = {
        "Easy  ·  3 × 3": 3,
        "Standard  ·  4 × 4": 4,
        "Challenge  ·  5 × 5": 5,
    }

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("HIT137 | TileShift")
        self.root.configure(bg=self.WINDOW_BG)
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._close_application)
        self.root.report_callback_exception = self._handle_tk_callback_error

        self.game: PuzzleGame | None = None
        self.current_image_path: str | None = None
        self.reference_photo: tk.PhotoImage | None = None
        self.puzzle_photo: tk.PhotoImage | None = None

        self.round_started_at: float | None = None
        self.round_elapsed = 0.0
        self.timer_job: str | None = None
        self.dialog_job: str | None = None
        self.completion_dialog_shown = False

        self.difficulty_var = tk.StringVar(value="Easy  ·  3 × 3")
        self.moves_var = tk.StringVar(value="0")
        self.tiles_left_var = tk.StringVar(value="0")
        self.hints_var = tk.StringVar(value="3")
        self.timer_var = tk.StringVar(value="00:00")
        self.progress_var = tk.DoubleVar(value=0.0)
        self.status_var = tk.StringVar(
            value="Choose a difficulty, then load a JPG, PNG or BMP image."
        )

        self._configure_theme()
        self._build_layout()
        self._bind_shortcuts()
        self._set_action_state(False)

    def run(self) -> None:
        self.root.mainloop()

    # ------------------------------------------------------------------
    # Window and theme
    # ------------------------------------------------------------------
    def _configure_theme(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("App.TFrame", background=self.WINDOW_BG)
        style.configure("Panel.TFrame", background=self.PANEL_BG)
        style.configure("Alt.TFrame", background=self.PANEL_ALT)

        style.configure(
            "Title.TLabel",
            background=self.WINDOW_BG,
            foreground=self.TEXT,
            font=("TkDefaultFont", 18, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=self.WINDOW_BG,
            foreground=self.MUTED,
            font=("TkDefaultFont", 10),
        )
        style.configure(
            "PanelTitle.TLabel",
            background=self.PANEL_BG,
            foreground=self.TEXT,
            font=("TkDefaultFont", 11, "bold"),
        )
        style.configure(
            "Caption.TLabel",
            background=self.PANEL_BG,
            foreground=self.MUTED,
            font=("TkDefaultFont", 9),
        )
        style.configure(
            "MetricNumber.TLabel",
            background=self.PANEL_ALT,
            foreground=self.TEXT,
            font=("TkDefaultFont", 15, "bold"),
        )
        style.configure(
            "MetricName.TLabel",
            background=self.PANEL_ALT,
            foreground=self.MUTED,
            font=("TkDefaultFont", 8),
        )
        style.configure(
            "Status.TLabel",
            background=self.PANEL_BG,
            foreground=self.TEXT,
            font=("TkDefaultFont", 9),
        )

        style.configure(
            "Primary.TButton",
            background=self.ACCENT,
            foreground="#07130F",
            borderwidth=0,
            padding=(12, 8),
            font=("TkDefaultFont", 9, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[("active", self.ACCENT_DARK), ("disabled", "#43515E")],
            foreground=[("disabled", "#9EABB7")],
        )
        style.configure(
            "Secondary.TButton",
            background=self.PANEL_ALT,
            foreground=self.TEXT,
            borderwidth=0,
            padding=(11, 8),
        )
        style.map(
            "Secondary.TButton",
            background=[("active", "#2A3A4F"), ("disabled", "#26313F")],
            foreground=[("disabled", "#728091")],
        )

        style.configure(
            "Puzzle.TCombobox",
            fieldbackground=self.PANEL_ALT,
            background=self.PANEL_ALT,
            foreground=self.TEXT,
            arrowcolor=self.TEXT,
            padding=5,
        )
        style.map(
            "Puzzle.TCombobox",
            fieldbackground=[("readonly", self.PANEL_ALT)],
            foreground=[("readonly", self.TEXT)],
        )
        style.configure(
            "Puzzle.Horizontal.TProgressbar",
            background=self.ACCENT,
            troughcolor="#2A3543",
            borderwidth=0,
            thickness=8,
        )

    def _build_layout(self) -> None:
        shell = ttk.Frame(self.root, style="App.TFrame", padding=16)
        shell.grid(row=0, column=0, sticky="nsew")

        heading = ttk.Frame(shell, style="App.TFrame")
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        heading.columnconfigure(1, weight=1)

        title_block = ttk.Frame(heading, style="App.TFrame")
        title_block.grid(row=0, column=0, sticky="nw")

        ttk.Label(title_block, text="TileShift", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            title_block,
            text="Image puzzle · OOP + Tkinter + OpenCV",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        self._build_control_guide(heading)

        controls = ttk.Frame(shell, style="Panel.TFrame", padding=12)
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        ttk.Label(controls, text="Difficulty", style="PanelTitle.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )

        self.difficulty_box = ttk.Combobox(
            controls,
            textvariable=self.difficulty_var,
            values=tuple(self.DIFFICULTIES.keys()),
            state="readonly",
            width=21,
            style="Puzzle.TCombobox",
        )
        self.difficulty_box.grid(row=0, column=1, padx=(0, 12))

        self.load_button = ttk.Button(
            controls,
            text="Load image",
            style="Primary.TButton",
            command=self._choose_image,
        )
        self.load_button.grid(row=0, column=2, padx=4)

        self.restart_button = ttk.Button(
            controls,
            text="Rescramble",
            style="Secondary.TButton",
            command=self._restart_round,
        )
        self.restart_button.grid(row=0, column=3, padx=4)

        self.hint_button = ttk.Button(
            controls,
            text="Hint",
            style="Secondary.TButton",
            command=self._use_hint,
        )
        self.hint_button.grid(row=0, column=4, padx=4)

        self.solve_button = ttk.Button(
            controls,
            text="Solve",
            style="Secondary.TButton",
            command=self._solve_round,
        )
        self.solve_button.grid(row=0, column=5, padx=(4, 0))

        image_row = ttk.Frame(shell, style="App.TFrame")
        image_row.grid(row=2, column=0, sticky="nsew")

        self.reference_panel, self.reference_canvas = self._build_image_panel(
            image_row,
            column=0,
            title="Reference",
            caption="Use this image as the target.",
        )
        self.puzzle_panel, self.puzzle_canvas = self._build_image_panel(
            image_row,
            column=1,
            title="Puzzle",
            caption="Only this image responds to player input.",
        )

        metrics = ttk.Frame(shell, style="Alt.TFrame", padding=10)
        metrics.grid(row=3, column=0, sticky="ew", pady=(12, 0))

        self._metric(metrics, 0, "Moves", self.moves_var)
        self._metric(metrics, 1, "Tiles left", self.tiles_left_var)
        self._metric(metrics, 2, "Hints left", self.hints_var)
        self._metric(metrics, 3, "Time", self.timer_var)

        progress_frame = ttk.Frame(metrics, style="Alt.TFrame")
        progress_frame.grid(row=0, column=4, rowspan=2, sticky="ew", padx=(18, 0))
        metrics.columnconfigure(4, weight=1)

        ttk.Label(
            progress_frame,
            text="Solved progress",
            style="MetricName.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            length=250,
            style="Puzzle.Horizontal.TProgressbar",
        )
        self.progress_bar.grid(row=1, column=0, sticky="ew")

        status_panel = ttk.Frame(shell, style="Panel.TFrame", padding=(12, 9))
        status_panel.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(
            status_panel,
            textvariable=self.status_var,
            style="Status.TLabel",
        ).grid(row=0, column=0, sticky="w")

        self.puzzle_canvas.bind("<Button-1>", self._on_left_click)
        self.puzzle_canvas.bind("<Shift-Button-1>", self._on_shift_left_click)
        self.puzzle_canvas.bind("<Button-3>", self._on_right_click)
        self.puzzle_canvas.bind("<Button-2>", self._on_right_click)
        self.puzzle_canvas.bind("<Control-Button-1>", self._on_right_click)

    def _build_control_guide(self, parent) -> None:
        """Place the main player controls in the previously unused top-right area."""
        card = tk.Frame(
            parent,
            bg=self.PANEL_BG,
            padx=10,
            pady=8,
            highlightthickness=1,
            highlightbackground="#2A3A4F",
        )
        card.grid(row=0, column=1, sticky="ne", padx=(24, 0))

        tk.Label(
            card,
            text="CONTROLS",
            bg=self.PANEL_BG,
            fg=self.ACCENT,
            font=("TkDefaultFont", 9, "bold"),
        ).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 5))

        controls = (
            ("LEFT CLICK", "Select / swap"),
            ("RIGHT CLICK", "Rotate 90°"),
            ("SHIFT + LEFT", "Flip"),
            ("H", "Hint"),
            ("R", "Rescramble"),
        )

        for index, (key, action) in enumerate(controls):
            row = 1 + index // 3
            column = (index % 3) * 2
            self._control_badge(card, row, column, key, action)

    def _control_badge(self, parent, row: int, column: int, key: str, action: str) -> None:
        tk.Label(
            parent,
            text=key,
            bg=self.CONTROL_KEY_BG,
            fg=self.TEXT,
            padx=7,
            pady=3,
            font=("TkDefaultFont", 8, "bold"),
        ).grid(row=row, column=column, sticky="w", padx=(0, 5), pady=2)
        tk.Label(
            parent,
            text=action,
            bg=self.PANEL_BG,
            fg=self.MUTED,
            font=("TkDefaultFont", 8),
        ).grid(row=row, column=column + 1, sticky="w", padx=(0, 12), pady=2)

    def _build_image_panel(self, parent, column, title, caption):
        panel = ttk.Frame(parent, style="Panel.TFrame", padding=10)
        panel.grid(row=0, column=column, padx=(0, 6) if column == 0 else (6, 0))

        ttk.Label(panel, text=title, style="PanelTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(panel, text=caption, style="Caption.TLabel").grid(
            row=1, column=0, sticky="w", pady=(2, 8)
        )

        canvas = tk.Canvas(
            panel,
            width=ImageProcessor.DEFAULT_MAX_SIDE,
            height=ImageProcessor.DEFAULT_MAX_SIDE,
            bg=self.CANVAS_BG,
            highlightthickness=0,
            bd=0,
        )
        canvas.grid(row=2, column=0)
        self._draw_empty_canvas(canvas, "No image loaded")
        return panel, canvas

    def _metric(self, parent, column, name, variable) -> None:
        box = ttk.Frame(parent, style="Alt.TFrame")
        box.grid(row=0, column=column, rowspan=2, padx=(0, 22), sticky="w")
        ttk.Label(box, textvariable=variable, style="MetricNumber.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(box, text=name, style="MetricName.TLabel").grid(
            row=1, column=0, sticky="w"
        )

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-o>", lambda _event: self._choose_image())
        self.root.bind("<Control-O>", lambda _event: self._choose_image())
        self.root.bind("<Key-h>", lambda _event: self._use_hint())
        self.root.bind("<Key-H>", lambda _event: self._use_hint())
        self.root.bind("<Key-r>", lambda _event: self._restart_round())
        self.root.bind("<Key-R>", lambda _event: self._restart_round())

    # ------------------------------------------------------------------
    # Round lifecycle
    # ------------------------------------------------------------------
    def _choose_image(self) -> None:
        try:
            path = filedialog.askopenfilename(
                title="Choose a puzzle image",
                filetypes=ImageProcessor.FILE_DIALOG_TYPES,
            )
        except tk.TclError as error:
            self._show_error("File dialog error", error)
            return

        if not path:
            self.status_var.set("Image selection cancelled. Current round unchanged.")
            return

        grid_size = self.DIFFICULTIES.get(self.difficulty_var.get())
        if grid_size not in (3, 4, 5):
            self._show_error(
                "Difficulty error",
                ValueError("Please choose Easy, Standard or Challenge before loading."),
            )
            return

        self._start_round(path, grid_size)

    def _start_round(self, path: str, grid_size: int) -> bool:
        try:
            new_game = PuzzleGame(path, grid_size)
        except ImageProcessingError as error:
            self._show_error("Image problem", error, "Could not load that image. Choose another file.")
            return False
        except (OSError, ValueError) as error:
            self._show_error("Cannot start puzzle", error, "The round was not started.")
            return False
        except Exception as error:
            self._show_error(
                "Unexpected error",
                error,
                "The puzzle could not be created. The previous round was left unchanged.",
            )
            return False

        self._cancel_dialog_job()
        self.game = new_game
        self.current_image_path = path
        self.completion_dialog_shown = False
        self._start_timer()
        self._set_action_state(True)
        self.status_var.set(
            f"New {grid_size} × {grid_size} puzzle ready. Restore the image on the right."
        )
        self._safe_refresh()
        return True

    def _restart_round(self) -> None:
        if self.game is None or not self.current_image_path:
            self.status_var.set("Load an image before using Rescramble.")
            return

        grid_size = self.game.grid_size
        path = self.current_image_path
        if self._start_round(path, grid_size):
            self.status_var.set("Image rescrambled. A new round has started.")

    def _solve_round(self) -> None:
        if not self._round_is_active():
            return

        try:
            self.game.solve()
        except Exception as error:
            self._show_error("Solve error", error, "The puzzle could not be solved automatically.")
            return

        self._stop_timer()
        self._set_action_state(False, keep_restart=True)
        self.status_var.set("Puzzle solved automatically. Moves reset to 0.")
        self._safe_refresh()
        self.completion_dialog_shown = True

        # Delay the modal dialog very slightly so all green ticks are painted first.
        self._schedule_dialog(
            120,
            "Puzzle solved",
            "The Solve button restored every tile to its home position and orientation.",
        )

    # ------------------------------------------------------------------
    # Player actions
    # ------------------------------------------------------------------
    def _on_left_click(self, event):
        # Shift + click and Control + click have their own actions. Ignore the
        # generic left-click path if Tk also reports one of those combinations.
        if event.state & 0x0001 or event.state & 0x0004:
            return "break"
        if not self._round_is_active():
            return "break"

        position = self._position_from_event(event)
        if position is None:
            self.status_var.set("Click inside the puzzle image to select a tile.")
            return "break"

        self._perform_move(
            lambda: self.game.select(position),
            move_message="Tiles swapped. Selection cleared.",
        )
        return "break"

    def _on_shift_left_click(self, event):
        if not self._round_is_active():
            return "break"

        position = self._position_from_event(event)
        if position is None:
            self.status_var.set("Click inside the puzzle image to flip a tile.")
            return "break"

        self._perform_move(
            lambda: self.game.flip(position),
            move_message="Tile flipped horizontally. Selection cleared.",
        )
        return "break"

    def _on_right_click(self, event):
        if not self._round_is_active():
            return "break"

        position = self._position_from_event(event)
        if position is None:
            self.status_var.set("Click inside the puzzle image to rotate a tile.")
            return "break"

        self._perform_move(
            lambda: self.game.rotate(position),
            move_message="Tile rotated 90° clockwise. Selection cleared.",
        )
        return "break"

    def _perform_move(self, action, move_message: str) -> None:
        """Run one player interaction and keep game state and GUI state synchronized."""
        if self.game is None:
            return

        moves_before = self.game.moves
        try:
            action()
        except (IndexError, ValueError) as error:
            self._show_error("Invalid move", error, "That move could not be applied.")
            return
        except Exception as error:
            self._show_error("Move error", error, "The move could not be completed.")
            return

        self._after_interaction(moves_before, move_message)

    def _use_hint(self) -> None:
        if not self._round_is_active():
            return

        try:
            hint_used = self.game.use_hint()
        except Exception as error:
            self._show_error("Hint error", error, "A hint could not be created.")
            return

        if hint_used:
            self.status_var.set(
                "Hint active: blue circles show an incorrect tile and its home position."
            )
            self._safe_refresh()
        elif self.game.hints_left == 0:
            self.status_var.set("All three hints have already been used for this image.")
            self._safe_refresh()
        else:
            self.status_var.set("No hint is needed because no incorrect tile is available.")

    def _after_interaction(self, moves_before: int, move_message: str) -> None:
        if self.game is None:
            return

        used_move = self.game.moves > moves_before

        # Refresh immediately after the operation. This draws the new tile state,
        # any green tick, counters and progress before completion handling begins.
        self._safe_refresh()

        if self.game.finished:
            self._complete_round()
            return

        if used_move:
            self.status_var.set(move_message)
        elif self.game.selected is not None:
            self.status_var.set(
                "Tile selected. Choose another tile to swap, or click it again to deselect."
            )
        else:
            self.status_var.set("Selection cleared.")

    def _complete_round(self) -> None:
        if self.game is None or self.completion_dialog_shown:
            return

        self._stop_timer()
        self._set_action_state(False, keep_restart=True)
        self.status_var.set(
            f"Completed in {self.game.moves} move(s) · time {self._format_time(self.round_elapsed)}."
        )

        # Render once more after the game has been marked complete. This guarantees
        # that the final green tick and 100% progress are part of the visible frame.
        self._safe_refresh()
        self.completion_dialog_shown = True

        dialog_text = (
            "You restored the complete image.\n\n"
            f"Moves: {self.game.moves}\n"
            f"Time: {self._format_time(self.round_elapsed)}"
        )
        self._schedule_dialog(120, "Puzzle complete", dialog_text)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _safe_refresh(self) -> None:
        try:
            self._refresh()
            self.root.update_idletasks()
        except (ImageProcessingError, tk.TclError) as error:
            self._show_error("Display error", error, "The puzzle state is safe, but the display could not be refreshed.")
        except Exception as error:
            self._show_error("Display error", error, "An unexpected display problem was handled.")

    def _refresh(self) -> None:
        if self.game is None:
            return

        self._render_reference()
        self._render_puzzle()
        self._update_metrics()

    def _render_reference(self) -> None:
        image = self.game.original_image
        self.reference_photo = self._photo_from_bgr(image)

        canvas = self.reference_canvas
        canvas.delete("all")
        canvas.create_image(0, 0, anchor="nw", image=self.reference_photo)

        if self.game.hint is not None:
            _current_position, home_position = self.game.hint
            self._draw_hint_circle(canvas, home_position)

    def _render_puzzle(self) -> None:
        image = self.game.current_image()
        self.puzzle_photo = self._photo_from_bgr(image)

        canvas = self.puzzle_canvas
        canvas.delete("all")
        canvas.create_image(0, 0, anchor="nw", image=self.puzzle_photo)

        self._draw_grid(canvas)

        total_tiles = self.game.grid_size ** 2
        for position in range(total_tiles):
            if self.game.is_tile_correct(position):
                self._draw_correct_tick(canvas, position)

        if self.game.selected is not None:
            self._draw_selection(canvas, self.game.selected)

        if self.game.hint is not None:
            current_position, _home_position = self.game.hint
            self._draw_hint_circle(canvas, current_position)

    def _draw_grid(self, canvas: tk.Canvas) -> None:
        side = self.game.original_image.shape[0]
        tile = self.game.tile_size
        for step in range(1, self.game.grid_size):
            coordinate = step * tile
            canvas.create_line(coordinate, 0, coordinate, side, fill=self.GRID, width=1)
            canvas.create_line(0, coordinate, side, coordinate, fill=self.GRID, width=1)

    def _draw_selection(self, canvas: tk.Canvas, position: int) -> None:
        x1, y1, x2, y2 = self._tile_box(position, inset=3)
        canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            outline=self.WARNING,
            width=4,
        )

    def _draw_correct_tick(self, canvas: tk.Canvas, position: int) -> None:
        x1, y1, _x2, _y2 = self._tile_box(position)
        size = self.game.tile_size
        start = (x1 + max(8, size * 0.08), y1 + max(18, size * 0.19))
        middle = (x1 + max(14, size * 0.15), y1 + max(25, size * 0.27))
        end = (x1 + max(30, size * 0.31), y1 + max(8, size * 0.08))
        canvas.create_line(*start, *middle, fill=self.GREEN, width=4, capstyle="round")
        canvas.create_line(*middle, *end, fill=self.GREEN, width=4, capstyle="round")

    def _draw_hint_circle(self, canvas: tk.Canvas, position: int) -> None:
        x1, y1, x2, y2 = self._tile_box(position)
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        radius = max(12, self.game.tile_size * 0.22)
        canvas.create_oval(
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius,
            outline=self.BLUE,
            width=4,
        )

    def _tile_box(self, position: int, inset: int = 0):
        row, column = divmod(position, self.game.grid_size)
        tile = self.game.tile_size
        x1 = column * tile + inset
        y1 = row * tile + inset
        x2 = (column + 1) * tile - inset
        y2 = (row + 1) * tile - inset
        return x1, y1, x2, y2

    def _update_metrics(self) -> None:
        total = self.game.grid_size ** 2
        incorrect = self.game.incorrect_count()
        correct = total - incorrect

        self.moves_var.set(str(self.game.moves))
        self.tiles_left_var.set(str(incorrect))
        self.hints_var.set(str(self.game.hints_left))
        self.progress_var.set((correct / total) * 100 if total else 0)

        if self.game.finished:
            self.hint_button.configure(state="disabled")
            self.solve_button.configure(state="disabled")
        else:
            self.hint_button.configure(
                state="normal" if self.game.hints_left > 0 else "disabled"
            )

    @staticmethod
    def _photo_from_bgr(image) -> tk.PhotoImage:
        data = ImageProcessor.to_tk_png_data(image)
        return tk.PhotoImage(data=data)

    # ------------------------------------------------------------------
    # Coordinates, timer, dialogs and state
    # ------------------------------------------------------------------
    def _position_from_event(self, event) -> int | None:
        if self.game is None:
            return None

        side = self.game.original_image.shape[0]
        x = int(event.x)
        y = int(event.y)

        # Off-image clicks are deliberately ignored.
        if x < 0 or y < 0 or x >= side or y >= side:
            return None

        column = x // self.game.tile_size
        row = y // self.game.tile_size
        if row >= self.game.grid_size or column >= self.game.grid_size:
            return None

        return row * self.game.grid_size + column

    def _round_is_active(self) -> bool:
        return self.game is not None and not self.game.finished

    def _set_action_state(self, active: bool, keep_restart: bool = False) -> None:
        state = "normal" if active else "disabled"
        self.hint_button.configure(state=state)
        self.solve_button.configure(state=state)

        restart_enabled = active or keep_restart or self.game is not None
        self.restart_button.configure(state="normal" if restart_enabled else "disabled")

        if active and self.game is not None and self.game.hints_left == 0:
            self.hint_button.configure(state="disabled")

    def _start_timer(self) -> None:
        self._cancel_timer_job()
        self.round_started_at = time.monotonic()
        self.round_elapsed = 0.0
        self.timer_var.set("00:00")
        self._tick_timer()

    def _tick_timer(self) -> None:
        if self.round_started_at is None or self.game is None or self.game.finished:
            return

        self.round_elapsed = time.monotonic() - self.round_started_at
        self.timer_var.set(self._format_time(self.round_elapsed))
        self.timer_job = self.root.after(250, self._tick_timer)

    def _stop_timer(self) -> None:
        if self.round_started_at is not None:
            self.round_elapsed = time.monotonic() - self.round_started_at
            self.timer_var.set(self._format_time(self.round_elapsed))
        self.round_started_at = None
        self._cancel_timer_job()

    def _cancel_timer_job(self) -> None:
        if self.timer_job is not None:
            try:
                self.root.after_cancel(self.timer_job)
            except tk.TclError:
                pass
            self.timer_job = None

    def _schedule_dialog(self, delay_ms: int, title: str, message: str) -> None:
        self._cancel_dialog_job()

        def show_dialog() -> None:
            self.dialog_job = None
            try:
                if self.root.winfo_exists():
                    messagebox.showinfo(title, message, parent=self.root)
            except tk.TclError:
                pass

        self.dialog_job = self.root.after(delay_ms, show_dialog)

    def _cancel_dialog_job(self) -> None:
        if self.dialog_job is not None:
            try:
                self.root.after_cancel(self.dialog_job)
            except tk.TclError:
                pass
            self.dialog_job = None

    def _show_error(self, title: str, error: Exception, status: str | None = None) -> None:
        message = str(error).strip() or type(error).__name__
        self.status_var.set(status or "An error was handled. The application is still running.")
        try:
            messagebox.showerror(title, message, parent=self.root)
        except tk.TclError:
            pass

    def _handle_tk_callback_error(self, exception_type, exception, traceback_object) -> None:
        # Tkinter routes uncaught callback exceptions here instead of terminating
        # the application or leaving a silent broken interaction.
        del exception_type, traceback_object
        self._show_error(
            "Interface error",
            exception,
            "An unexpected interface error was handled. You can continue or load a new image.",
        )

    @staticmethod
    def _format_time(seconds: float) -> str:
        seconds = max(0, int(seconds))
        minutes, seconds = divmod(seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"

    def _draw_empty_canvas(self, canvas: tk.Canvas, message: str) -> None:
        canvas.delete("all")
        center = ImageProcessor.DEFAULT_MAX_SIDE // 2
        canvas.create_text(
            center,
            center,
            text=message,
            fill=self.MUTED,
            font=("TkDefaultFont", 11),
        )

    def _close_application(self) -> None:
        self._cancel_timer_job()
        self._cancel_dialog_job()
        try:
            self.root.destroy()
        except tk.TclError:
            pass
