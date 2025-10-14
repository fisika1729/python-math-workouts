#!/usr/bin/env python3
# Collatz Matrix Rain — Pygame (full-digit blocks, slower, clearer, with logging)

import sys
import argparse
import random
import pygame

def collatz_step(n: int) -> int:
    return n // 2 if n % 2 == 0 else 3 * n + 1

def collatz_generator(start: int):
    n = start
    while True:
        yield n
        if n == 1:
            break
        n = collatz_step(n)

DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

def int_to_base(n: int, base: int = 36) -> str:
    if n == 0:
        return "0"
    s = []
    x = n
    sign = ""
    if x < 0:
        sign = "-"
        x = -x
    while x:
        x, r = divmod(x, base)
        s.append(DIGITS[r])
    s = "".join(reversed(s))
    return sign + s

class MatrixColumn:
    def __init__(
        self,
        x_index: int,
        px_width: int,
        px_height: int,
        font,
        font_size: int,
        speed_rows_per_sec: float,
        tail_length: int,
        bottom_fade_px: int,
        spawn_min_ms: int,
        spawn_max_ms: int,
        block_gap_rows: int,
        min_digits: int,
        max_digits: int,
        bold: bool,
        shadow_offset: int,
        fixed_start: int | None = None
    ):
        self.x_index = x_index
        self.w = px_width
        self.h = px_height
        self.font = font
        self.font_size = font_size
        self.speed = speed_rows_per_sec
        self.tail_length = tail_length
        self.bottom_fade_px = max(0, bottom_fade_px)
        self.spawn_min_ms = max(0, spawn_min_ms)
        self.spawn_max_ms = max(self.spawn_min_ms, spawn_max_ms)
        self.block_gap_rows = max(0, block_gap_rows)
        self.min_digits = max(10, min_digits)
        self.max_digits = max(self.min_digits, max_digits)
        self.fixed_start = fixed_start
        self.bold = bold
        self.shadow_offset = max(0, shadow_offset)

        self.font.set_bold(self.bold)

        self.x = self.x_index * self.font_size

        self.active = False
        self.sequence_finished = False
        self.head_row = 0.0
        self.row_accum = 0.0
        self.rows_until_next_block = 0
        self.char_buffer: list[str] = []
        self.collatz = None
        self.t_next_spawn = 0

    def _random_start_with_min_digits(self) -> int:
        if self.fixed_start is not None:
            return max(1, int(self.fixed_start))
        k = random.randint(self.min_digits, self.max_digits)
        lo = 10 ** (k - 1)
        hi = 10 ** k - 1
        return random.randrange(lo, hi + 1)

    def schedule_next(self, now_ms: int):
        wait = random.randint(self.spawn_min_ms, self.spawn_max_ms)
        self.t_next_spawn = now_ms + wait
        self.active = False
        self.sequence_finished = False
        self.char_buffer.clear()

    def start_new_sequence(self, now_ms: int):
        start = self._random_start_with_min_digits()
        print(f"Column {self.x_index} start: {start}", flush=True)
        self.collatz = collatz_generator(start)
        rows_above = random.uniform(2, self.h // self.font_size // 4 + 4)
        self.head_row = -rows_above
        self.row_accum = 0.0
        self.rows_until_next_block = 0
        self.char_buffer.clear()
        self.active = True
        self.sequence_finished = False

    def _emit_block_from_value(self, n: int):
        digits = list(str(n))
        for ch in digits:
            self.char_buffer.insert(0, ch)
        max_rows_on_screen = (self.h // self.font_size) + self.tail_length + 16
        if len(self.char_buffer) > max_rows_on_screen:
            self.char_buffer = self.char_buffer[:max_rows_on_screen]
        self.rows_until_next_block = len(digits) + self.block_gap_rows

    def update(self, dt: float, now_ms: int):
        if not self.active:
            if now_ms >= self.t_next_spawn:
                self.start_new_sequence(now_ms)
            return

        delta_rows = self.speed * dt
        self.head_row += delta_rows
        self.row_accum += delta_rows

        while self.row_accum >= 1.0:
            self.row_accum -= 1.0
            if not self.sequence_finished and self.rows_until_next_block <= 0:
                try:
                    n = next(self.collatz)
                    self._emit_block_from_value(n)
                except StopIteration:
                    self.sequence_finished = True
            else:
                self.rows_until_next_block = max(0, self.rows_until_next_block - 1)

        total_rows = len(self.char_buffer)
        if total_rows > 0:
            top_y = int(self.head_row * self.font_size) - (total_rows - 1) * self.font_size
            if top_y > self.h + self.font_size:
                self.schedule_next(now_ms)

    def draw(self, surface: pygame.Surface, head_color=(240, 255, 240), base_green=(0, 255, 65)):
        if not self.active:
            return

        head_y = int(self.head_row * self.font_size)
        fade_start_y = self.h - self.bottom_fade_px if self.bottom_fade_px > 0 else self.h

        # Shadow color for readability
        shadow_color = (20, 60, 20)

        for i, ch in enumerate(self.char_buffer):
            y = head_y - i * self.font_size
            if y < -self.font_size:
                continue
            if y > self.h:
                break

            if i == 0:
                color = head_color
                alpha = 255
            else:
                decay = max(0.0, 1.0 - (i / self.tail_length)) if self.tail_length > 0 else 0.0
                decay = decay ** 1.5
                g = int(base_green[1] * (0.45 + 0.55 * decay))
                color = (0, g, int(base_green[2] * decay * 0.5))
                alpha = int(255 * decay)

            if y >= fade_start_y and self.bottom_fade_px > 0:
                m = max(0.0, min(1.0, (self.h - y) / self.bottom_fade_px))
                alpha = int(alpha * m)

            if alpha <= 0:
                continue

            # Drop shadow behind the digit (draw first)
            if self.shadow_offset > 0:
                shadow = self.font.render(ch, True, shadow_color)
                shadow.set_alpha(min(220, alpha))
                surface.blit(shadow, (self.x + self.shadow_offset, y + self.shadow_offset))

            glyph = self.font.render(ch, True, color)
            glyph.set_alpha(alpha)
            surface.blit(glyph, (self.x, y))

def main():
    parser = argparse.ArgumentParser(description="Collatz Matrix Rain (full-digit blocks, readable)")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--font-size", type=int, default=28)
    parser.add_argument("--columns", type=int, default=48)
    parser.add_argument("--speed", type=float, default=10.0, help="Rows per second per column (lower = slower)")
    parser.add_argument("--tail", type=int, default=24, help="Trail length in rows")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--start", type=str, default=None, help="Fixed start integer for all spawns (decimal, >=10 digits)")
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--spawn-min-ms", type=int, default=900)
    parser.add_argument("--spawn-max-ms", type=int, default=5000)
    parser.add_argument("--bottom-fade-px", type=int, default=140)
    parser.add_argument("--trail-alpha", type=int, default=60, help="Screen fade alpha per frame (0..255, higher = less trail)")
    parser.add_argument("--block-gap-rows", type=int, default=2, help="Blank rows between successive values")
    parser.add_argument("--min-digits", type=int, default=10, help="Minimum starting digits")
    parser.add_argument("--max-digits", type=int, default=26, help="Maximum starting digits")
    # Bold on by default, allow disabling via --no-bold
    parser.add_argument("--bold", dest="bold", action="store_true")
    parser.add_argument("--no-bold", dest="bold", action="store_false")
    parser.set_defaults(bold=True)
    parser.add_argument("--shadow-offset", type=int, default=2, help="Drop shadow pixel offset (0 disables)")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    pygame.init()
    pygame.display.set_caption("Collatz Matrix Rain")
    screen = pygame.display.set_mode((args.width, args.height), pygame.SRCALPHA)
    clock = pygame.time.Clock()

    try:
        font = pygame.font.SysFont("Consolas,Menlo,Monaco,Courier New,monospace", args.font_size)
    except Exception:
        font = pygame.font.SysFont(None, args.font_size)

    cols_fit = args.width // args.font_size
    columns_count = min(args.columns, cols_fit)

    fixed_start = None
    if args.start is not None:
        try:
            fixed_start = int(args.start, 10)
            if len(str(abs(fixed_start))) < max(10, args.min_digits):
                print("Fixed start must have at least 10 digits", file=sys.stderr)
                return
            if fixed_start < 1:
                fixed_start = 1
        except Exception:
            print("Invalid --start; must be a decimal integer", file=sys.stderr)
            return

    grid_indices = list(range(cols_fit))
    step = max(1, len(grid_indices) // max(1, columns_count))
    chosen_indices = grid_indices[::step][:columns_count]

    columns = []
    for x_idx in chosen_indices:
        col = MatrixColumn(
            x_index=x_idx,
            px_width=args.width,
            px_height=args.height,
            font=font,
            font_size=args.font_size,
            speed_rows_per_sec=args.speed * (0.9 + 0.25 * random.random()),
            tail_length=args.tail,
            bottom_fade_px=args.bottom_fade_px,
            spawn_min_ms=args.spawn_min_ms,
            spawn_max_ms=args.spawn_max_ms,
            block_gap_rows=args.block_gap_rows,
            min_digits=args.min_digits,
            max_digits=args.max_digits,
            bold=args.bold,
            shadow_offset=args.shadow_offset,
            fixed_start=fixed_start
        )
        columns.append(col)

    fade_surface = pygame.Surface((args.width, args.height), pygame.SRCALPHA)
    fade_surface.fill((0, 0, 0, max(0, min(255, args.trail_alpha))))

    now_ms = pygame.time.get_ticks()
    for col in columns:
        col.t_next_spawn = now_ms + random.randint(0, max(args.spawn_max_ms, args.spawn_min_ms))
        col.active = False

    running = True
    while running:
        dt = clock.tick(args.fps) / 1000.0
        now_ms = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.blit(fade_surface, (0, 0))

        for col in columns:
            col.update(dt, now_ms)
            col.draw(screen)

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
