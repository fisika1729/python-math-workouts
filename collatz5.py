#!/usr/bin/env python3
# Collatz Vertical Rain — multiple chains, vertical per-number columns, next starts at halfway

import sys
import argparse
import random
import pygame

def collatz_step(n: int) -> int:
    # Strict Collatz rule on integers: even -> n/2, odd -> 3n+1
    return n // 2 if n % 2 == 0 else 3 * n + 1

class VerticalNumberStream:
    """
    Emits one integer's decimal digits vertically down a fixed column.
    - Digits appear one per row step in that same column.
    - Brightness increases with y (brightest near bottom).
    - When the emission head reaches half the screen height, the next Collatz value may be spawned.
    """
    def __init__(self, value: int, column: int, cols_fit: int, row_px: int, screen_h: int,
                 rows_per_sec: float, digit_gap_rows: int, label: str = ""):
        self.value = value
        self.digits = list(str(value))                # render-only; math uses integer value
        self.column = max(0, min(column, cols_fit - 1))
        self.row_px = row_px
        self.screen_h = screen_h
        self.rows_per_sec = rows_per_sec
        self.digit_gap_rows = max(0, digit_gap_rows)

        # Emission/animation state
        self.head_row = -2.0
        self.row_accum = 0.0
        self.rows_until_next_digit = 0
        self.emit_index = 0
        self.done_emitting = False
        self.spawned_next = False

        # Visible buffer: head at index 0
        self.char_buffer: list[str] = []

        # Log this stream's start value
        print(f"{label}start: {self.value}", flush=True)

    def update(self, dt: float):
        # Advance in row units; spawn one digit per row step
        delta_rows = self.rows_per_sec * dt
        self.head_row += delta_rows
        self.row_accum += delta_rows

        while self.row_accum >= 1.0 and not self.done_emitting:
            self.row_accum -= 1.0
            if self.rows_until_next_digit <= 0:
                if self.emit_index < len(self.digits):
                    self.char_buffer.insert(0, self.digits[self.emit_index])
                    self.emit_index += 1
                    self.rows_until_next_digit = 1 + self.digit_gap_rows
                else:
                    self.done_emitting = True
            else:
                self.rows_until_next_digit -= 1

    def should_spawn_next(self) -> bool:
        # Trigger next number once head reaches mid-screen
        head_y = int(self.head_row * self.row_px)
        return head_y >= (self.screen_h // 2)

    def offscreen(self) -> bool:
        # When the entire vertical buffer has moved below the screen, remove the stream
        if not self.char_buffer:
            return False
        top_y = int(self.head_row * self.row_px) - (len(self.char_buffer) - 1) * self.row_px
        return top_y > self.screen_h + self.row_px

    def draw(self, surface: pygame.Surface, font: pygame.font.Font,
             head_rgb=(220, 255, 220), base_green=(0, 255, 65), height_px: int = 1080):
        # Brightness ramp with y: darkest near top, brightest near bottom
        def brightness(y_px: int) -> float:
            t = max(0.0, min(1.0, y_px / height_px))
            return 0.35 + 0.65 * (t ** 1.2)

        head_y = int(self.head_row * self.row_px)
        x_px = self.column * self.row_px

        for i, ch in enumerate(self.char_buffer):
            y_px = head_y - i * self.row_px
            if y_px < -self.row_px:
                continue
            if y_px > self.screen_h:
                break

            m = brightness(y_px)
            r = int(head_rgb[0] * m * 0.8)
            g = int(base_green[1] * m)
            b = int(base_green[2] * m * 0.5)
            alpha = int(255 * m)

            glyph = font.render(ch, True, (r, g, b))  # antialiased text for clarity
            glyph.set_alpha(alpha)
            surface.blit(glyph, (x_px, y_px))

class CollatzVerticalRain:
    def __init__(self, args):
        self.args = args

        pygame.init()
        pygame.display.set_caption("Collatz Vertical Rain — multiple chains, bright at bottom")
        self.screen = pygame.display.set_mode((args.width, args.height), pygame.SRCALPHA)
        self.clock = pygame.time.Clock()

        # Smaller monospace font; no shadow/bold
        try:
            self.font = pygame.font.SysFont("Consolas,Menlo,Monaco,Courier New,monospace", args.font_size)
        except Exception:
            self.font = pygame.font.SysFont(None, args.font_size)

        # Grid sizing
        self.row_px = args.font_size
        self.cols_fit = max(1, args.width // self.row_px)
        self.rows_fit = max(1, args.height // self.row_px)

        # Screen-wide trail fade
        self.fade_surface = pygame.Surface((args.width, args.height), pygame.SRCALPHA)
        self.fade_surface.fill((0, 0, 0, max(0, min(255, args.trail_alpha))))

        # Active vertical streams
        self.streams: list[VerticalNumberStream] = []

        # Seed multiple independent Collatz chains at distinct columns if possible
        start_columns = self._pick_distinct_columns(args.initial_chains)
        for idx, col in enumerate(start_columns):
            n0 = self._seed_value()
            self.streams.append(
                VerticalNumberStream(
                    value=n0,
                    column=col,
                    cols_fit=self.cols_fit,
                    row_px=self.row_px,
                    screen_h=args.height,
                    rows_per_sec=args.speed,
                    digit_gap_rows=args.digit_gap_rows,
                    label=f"Chain {idx} "
                )
            )

    def _pick_distinct_columns(self, count: int) -> list[int]:
        cols = list(range(self.cols_fit))
        random.shuffle(cols)
        if count <= self.cols_fit:
            return cols[:count]
        # If more chains than columns, wrap with repeats
        out = []
        while len(out) < count:
            out.extend(cols)
        return out[:count]

    def _seed_value(self) -> int:
        if self.args.start is not None:
            n = int(self.args.start, 10)
            return max(1, n)
        dmin = max(10, self.args.min_digits)
        dmax = max(dmin, self.args.max_digits)
        k = random.randint(dmin, dmax)
        lo = 10 ** (k - 1)
        hi = 10 ** k - 1
        return random.randrange(lo, hi + 1)

    def _choose_next_column(self, avoid_col: int | None) -> int:
        # Prefer a column different from the parent if possible
        if self.cols_fit <= 1 or avoid_col is None:
            return random.randrange(0, self.cols_fit)
        choices = [c for c in range(self.cols_fit) if c != avoid_col]
        return random.choice(choices) if choices else avoid_col

    def _spawn_next_from(self, parent: VerticalNumberStream):
        # Compute next Collatz integer strictly and start it immediately while parent continues
        nxt = collatz_step(parent.value)
        col = self._choose_next_column(parent.column)
        child = VerticalNumberStream(
            value=nxt,
            column=col,
            cols_fit=self.cols_fit,
            row_px=self.row_px,
            screen_h=self.args.height,
            rows_per_sec=self.args.speed,
            digit_gap_rows=self.args.digit_gap_rows,
            label="Next "
        )
        self.streams.append(child)

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(self.args.fps) / 1000.0  # stable pacing
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            # Fade trails
            self.screen.blit(self.fade_surface, (0, 0))

            # Update existing streams; spawn next numbers at mid-screen
            for s in list(self.streams):
                s.update(dt)
                if not s.spawned_next and s.should_spawn_next():
                    s.spawned_next = True
                    self._spawn_next_from(s)

            # Remove streams whose entire stack is offscreen to keep things tidy
            self.streams = [s for s in self.streams if not s.offscreen()]

            # Draw
            for s in self.streams:
                s.draw(self.screen, self.font, height_px=self.args.height)

            pygame.display.flip()

        pygame.quit()

def main():
    parser = argparse.ArgumentParser(description="Collatz vertical rain — multi-column, next starts at halfway")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--font-size", type=int, default=20, help="Digit height in pixels")
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--speed", type=float, default=8.0, help="Rows per second; lower = slower")
    parser.add_argument("--trail-alpha", type=int, default=60, help="Screen fade alpha per frame (0..255)")
    parser.add_argument("--digit-gap-rows", type=int, default=0, help="Blank rows between emitted digits")
    parser.add_argument("--initial-chains", type=int, default=3, help="How many independent starting columns")
    parser.add_argument("--min-digits", type=int, default=10, help="Minimum starting digits")
    parser.add_argument("--max-digits", type=int, default=26, help="Maximum starting digits")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--start", type=str, default=None, help="Optional fixed starting integer (>=10 digits) for all chains")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    app = CollatzVerticalRain(args)
    app.run()

if __name__ == "__main__":
    main()
