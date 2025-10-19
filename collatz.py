#!/usr/bin/env python3
# Collatz Vertical Rain — dense multi-column fill with per-digit bottom culling

import sys
import argparse
import random
import pygame

def collatz_step(n: int) -> int:
    # Strict Collatz rule on integers
    return n // 2 if n % 2 == 0 else 3 * n + 1

class VerticalNumberStream:
    """
    Emits one integer's decimal digits vertically down a fixed column.
    - Digits appear one per row step in that same column.
    - Brightness increases with vertical position (brightest near bottom).
    - When the emission head reaches half the screen height, the next Collatz value may be spawned.
    - Digits are culled individually as they reach the bottom edge.
    """
    def __init__(self, value: int, column: int, cols_fit: int, row_px: int, screen_h: int,
                 rows_per_sec: float, digit_gap_rows: int, label: str = ""):
        self.value = value
        self.digits = list(str(value))         # render-only
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

        # Visible stack: newest at index 0
        self.char_buffer: list[str] = []

        print(f"{label}start: {self.value}", flush=True)

    def update(self, dt: float):
        delta_rows = self.rows_per_sec * dt
        self.head_row += delta_rows
        self.row_accum += delta_rows

        # Emit digits one-by-one per row
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

        # Per-digit bottom culling: remove exactly one tail digit when it hits the bottom
        if self.char_buffer:
            tail_index = len(self.char_buffer) - 1
            tail_y = int(self.head_row * self.row_px) - tail_index * self.row_px
            if tail_y >= self.screen_h - 1:
                self.char_buffer.pop()  # drop the bottom-most digit

    def should_spawn_next(self) -> bool:
        head_y = int(self.head_row * self.row_px)
        return head_y >= (self.screen_h // 2)

    def offscreen(self) -> bool:
        # Stream ends only when all digits have been emitted and the buffer is empty
        return self.done_emitting and not self.char_buffer

    def draw(self, surface: pygame.Surface, font: pygame.font.Font,
             head_rgb=(220, 255, 220), base_green=(0, 255, 65), height_px: int = 1080):
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

            glyph = font.render(ch, True, (r, g, b))
            glyph.set_alpha(alpha)
            surface.blit(glyph, (x_px, y_px))

class CollatzVerticalRain:
    def __init__(self, args):
        self.args = args

        pygame.init()
        pygame.display.set_caption("Collatz Vertical Rain — dense fill, per-digit cull")
        self.screen = pygame.display.set_mode((args.width, args.height), pygame.SRCALPHA)
        self.clock = pygame.time.Clock()

        try:
            self.font = pygame.font.SysFont("Consolas,Menlo,Monaco,Courier New,monospace", args.font_size)
        except Exception:
            self.font = pygame.font.SysFont(None, args.font_size)

        # Grid geometry
        self.row_px = args.font_size
        self.cols_fit = max(1, args.width // self.row_px)
        self.rows_fit = max(1, args.height // self.row_px)

        # Screen-wide trail fade
        self.fade_surface = pygame.Surface((args.width, args.height), pygame.SRCALPHA)
        self.fade_surface.fill((0, 0, 0, max(0, min(255, args.trail_alpha))))

        # Streams
        self.streams: list[VerticalNumberStream] = []

        # Fill one stream per column initially
        init_cols = list(range(self.cols_fit))
        random.shuffle(init_cols)
        for idx, col in enumerate(init_cols[:self.cols_fit]):
            self.streams.append(
                VerticalNumberStream(
                    value=self._seed_value(),
                    column=col,
                    cols_fit=self.cols_fit,
                    row_px=self.row_px,
                    screen_h=args.height,
                    rows_per_sec=args.speed,
                    digit_gap_rows=args.digit_gap_rows,
                    label=f"Seed {idx} "
                )
            )

        # Target concurrency based on density
        self.target_active = max(self.cols_fit, int(self.cols_fit * args.density))

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
        if self.cols_fit <= 1 or avoid_col is None:
            return random.randrange(0, self.cols_fit)
        choices = [c for c in range(self.cols_fit) if c != avoid_col]
        return random.choice(choices) if choices else avoid_col

    def _spawn_next_from(self, parent: VerticalNumberStream):
        nxt = collatz_step(parent.value)  # strict integer step
        col = self._choose_next_column(parent.column)
        self.streams.append(
            VerticalNumberStream(
                value=nxt,
                column=col,
                cols_fit=self.cols_fit,
                row_px=self.row_px,
                screen_h=self.args.height,
                rows_per_sec=self.args.speed,
                digit_gap_rows=self.args.digit_gap_rows,
                label="Next "
            )
        )

    def _top_up_density(self):
        deficit = self.target_active - len(self.streams)
        for _ in range(max(0, deficit)):
            col = random.randrange(0, self.cols_fit)
            self.streams.append(
                VerticalNumberStream(
                    value=self._seed_value(),
                    column=col,
                    cols_fit=self.cols_fit,
                    row_px=self.row_px,
                    screen_h=self.args.height,
                    rows_per_sec=self.args.speed,
                    digit_gap_rows=self.args.digit_gap_rows,
                    label="Seed "
                )
            )

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(self.args.fps) / 1000.0  # stable pacing
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            # Fade trails
            self.screen.blit(self.fade_surface, (0, 0))

            # Update and spawn next numbers at mid-screen
            for s in list(self.streams):
                s.update(dt)
                if not s.spawned_next and s.should_spawn_next():
                    s.spawned_next = True
                    self._spawn_next_from(s)

            # Remove only streams that have emitted all digits and whose buffer is empty
            self.streams = [s for s in self.streams if not s.offscreen()]

            # Keep density high to avoid blanks
            self._top_up_density()

            # Draw
            for s in self.streams:
                s.draw(self.screen, self.font, height_px=self.args.height)

            pygame.display.flip()

        pygame.quit()

def main():
    parser = argparse.ArgumentParser(description="Collatz vertical rain — dense fill, per-digit bottom removal")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--font-size", type=int, default=20, help="Digit height in pixels")
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--speed", type=float, default=8.0, help="Rows per second; lower = slower")
    parser.add_argument("--trail-alpha", type=int, default=50, help="Screen fade alpha per frame (0..255)")
    parser.add_argument("--digit-gap-rows", type=int, default=0, help="Blank rows between emitted digits")
    parser.add_argument("--density", type=float, default=1.25, help="Target active streams = density × columns")
    parser.add_argument("--min-digits", type=int, default=10, help="Minimum starting digits")
    parser.add_argument("--max-digits", type=int, default=26, help="Maximum starting digits")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--start", type=str, default=None, help="Optional fixed starting integer (>=10 digits)")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    app = CollatzVerticalRain(args)
    app.run()

if __name__ == "__main__":
    main()
