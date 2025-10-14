#!/usr/bin/env python3
# Collatz Matrix Rain — Pygame (discrete spawns per column)

import sys
import argparse
import random
import pygame

# ---------------------------
# Collatz logic (big integers)
# ---------------------------

def collatz_step(n: int) -> int:
    if n % 2 == 0:
        return n // 2
    else:
        return 3 * n + 1

def collatz_generator(start: int):
    n = start
    while True:
        yield n
        if n == 1:
            break
        n = collatz_step(n)

# ---------------------------
# Utilities
# ---------------------------

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

# ---------------------------
# Matrix Rain Column (discrete spawns)
# ---------------------------

class MatrixColumn:
    def __init__(
        self,
        x_index: int,
        px_width: int,
        px_height: int,
        font,
        font_size: int,
        speed_rows_per_sec: float,
        base: int,
        tail_length: int,
        bottom_fade_px: int,
        spawn_min_ms: int,
        spawn_max_ms: int,
        fixed_start: int | None = None
    ):
        self.x_index = x_index
        self.w = px_width
        self.h = px_height
        self.font = font
        self.font_size = font_size
        self.speed = speed_rows_per_sec
        self.base = base
        self.tail_length = tail_length
        self.bottom_fade_px = max(0, bottom_fade_px)
        self.spawn_min_ms = max(0, spawn_min_ms)
        self.spawn_max_ms = max(self.spawn_min_ms, spawn_max_ms)
        self.fixed_start = fixed_start

        self.x = self.x_index * self.font_size

        # State
        self.active = False
        self.head_row = 0.0
        self.row_accum = 0.0
        self.char_buffer: list[str] = []
        self.collatz = None
        self.t_next_spawn = 0

    def _random_start_value(self) -> int:
        if self.fixed_start is not None:
            return max(1, int(self.fixed_start))
        n = random.getrandbits(256)
        if random.random() < 0.5:
            n |= 1  # sometimes odd
        return max(1, n)

    def schedule_next(self, now_ms: int):
        wait = random.randint(self.spawn_min_ms, self.spawn_max_ms)
        self.t_next_spawn = now_ms + wait
        self.active = False
        self.char_buffer.clear()

    def start_new_sequence(self, now_ms: int):
        start = self._random_start_value()
        self.collatz = collatz_generator(start)
        # Start slightly above top so head flows into view
        rows_above = random.uniform(2, self.h // self.font_size // 4 + 4)
        self.head_row = -rows_above
        self.row_accum = 0.0
        self.char_buffer.clear()
        self.active = True

    def update(self, dt: float, now_ms: int):
        # Handle idle -> active transition
        if not self.active:
            if now_ms >= self.t_next_spawn:
                self.start_new_sequence(now_ms)
            return

        # Active stream: advance head and push digits
        delta_rows = self.speed * dt
        self.head_row += delta_rows
        self.row_accum += delta_rows

        while self.row_accum >= 1.0:
            self.row_accum -= 1.0
            try:
                n = next(self.collatz)
                s = int_to_base(n, self.base)
                ch = s[-1]
                self.char_buffer.insert(0, ch)
                # Keep only as much as can be seen + tail slack
                max_rows_on_screen = (self.h // self.font_size) + self.tail_length + 8
                if len(self.char_buffer) > max_rows_on_screen:
                    self.char_buffer = self.char_buffer[:max_rows_on_screen]
            except StopIteration:
                # Collatz sequence finished at 1; allow the stream to continue moving
                # until fully off-screen, then deactivate.
                pass

        # If head and entire tail are below screen, end this stream and schedule next
        total_rows = len(self.char_buffer)
        last_row_y = int(self.head_row * self.font_size) - (total_rows - 1) * self.font_size
        if total_rows > 0 and last_row_y > self.h + self.font_size:
            # Stop drawing; global fade will clear the remnants
            self.schedule_next(now_ms)

    def draw(self, surface: pygame.Surface, head_color=(180, 255, 180), base_green=(0, 255, 65)):
        if not self.active:
            return

        head_y = int(self.head_row * self.font_size)
        fade_start_y = self.h - self.bottom_fade_px if self.bottom_fade_px > 0 else self.h

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
                g = int(base_green[1] * (0.35 + 0.65 * decay))
                color = (0, g, int(base_green[2] * decay * 0.6))
                alpha = int(255 * decay)

            # Bottom fade multiplier
            if y >= fade_start_y and self.bottom_fade_px > 0:
                m = max(0.0, min(1.0, (self.h - y) / self.bottom_fade_px))
                alpha = int(alpha * m)

            if alpha <= 0:
                continue

            glyph = self.font.render(ch, True, color)
            glyph.set_alpha(alpha)
            surface.blit(glyph, (self.x, y))

# ---------------------------
# Main app
# ---------------------------

def main():
    parser = argparse.ArgumentParser(description="Collatz Matrix Rain (discrete spawns per column)")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--font-size", type=int, default=20)
    parser.add_argument("--columns", type=int, default=64)
    parser.add_argument("--speed", type=float, default=22.0, help="Rows per second per column")
    parser.add_argument("--base", type=int, default=36, help="Base for digit mapping (2..36)")
    parser.add_argument("--tail", type=int, default=30, help="Tail length in characters")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--start", type=str, default=None, help="Fixed start integer for all spawns (decimal)")
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--spawn-min-ms", type=int, default=600, help="Min idle time between spawns per column")
    parser.add_argument("--spawn-max-ms", type=int, default=4000, help="Max idle time between spawns per column")
    parser.add_argument("--bottom-fade-px", type=int, default=120, help="Extra fade near bottom edge in pixels")
    parser.add_argument("--trail-alpha", type=int, default=30, help="Screen fade alpha per frame (0..255)")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    pygame.init()
    pygame.display.set_caption("Collatz Matrix Rain")
    screen = pygame.display.set_mode((args.width, args.height), pygame.SRCALPHA)
    clock = pygame.time.Clock()

    # Font: try monospace
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
            if fixed_start < 1:
                fixed_start = 1
        except Exception:
            print("Invalid --start; must be a decimal integer", file=sys.stderr)
            return

    # Choose grid x indices spread across width
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
            speed_rows_per_sec=args.speed * (0.85 + 0.3 * random.random()),
            base=max(2, min(36, args.base)),
            tail_length=args.tail,
            bottom_fade_px=args.bottom_fade_px,
            spawn_min_ms=args.spawn_min_ms,
            spawn_max_ms=args.spawn_max_ms,
            fixed_start=fixed_start
        )
        columns.append(col)

    # Semi-transparent fade surface for trails
    fade_surface = pygame.Surface((args.width, args.height), pygame.SRCALPHA)
    fade_surface.fill((0, 0, 0, max(0, min(255, args.trail_alpha))))

    # Prime initial schedules with random offsets so columns don't sync
    now_ms = pygame.time.get_ticks()
    for col in columns:
        # Stagger initial spawns with an immediate schedule somewhere in [0, spawn_max]
        col.t_next_spawn = now_ms + random.randint(0, max(args.spawn_max_ms, args.spawn_min_ms))
        col.active = False

    running = True
    while running:
        dt = clock.tick(args.fps) / 1000.0
        now_ms = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Apply screen-wide fade for trails
        screen.blit(fade_surface, (0, 0))

        # Update and draw columns
        for col in columns:
            col.update(dt, now_ms)
            col.draw(screen)

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
