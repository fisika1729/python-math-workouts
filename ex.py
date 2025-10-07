#!/usr/bin/env python3
# Collatz Matrix Rain — Pygame
# Requirements: pygame (pip install pygame)

import sys
import argparse
import random
import pygame
import numpy

# ---------------------------
# Collatz logic (big integers)
# ---------------------------

def collatz_step(n: int) -> int:
    # n must be a positive integer
    if n % 2 == 0:
        return n // 2
    else:
        return 3 * n + 1

def collatz_generator(start: int):
    # Infinite generator that cycles through the full sequence until 1, then restarts from a new random seed
    n = start
    while True:
        yield n
        if n == 1:
            # When reaching 1, pick a new large random seed to keep the stream interesting
            n = random.getrandbits(128) | 1  # ensure odd sometimes
            continue
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
# Matrix Rain Column
# ---------------------------

class MatrixColumn:
    def __init__(
        self,
        x_index: int,
        px_width: int,
        px_height: int,
        font,
        collatz_start: int,
        font_size: int = 20,
        speed_rows_per_sec: float = 20.0,
        base: int = 36,
        tail_length: int = 30,
        max_char_buffer: int = 100
    ):
        self.x_index = x_index
        self.w = px_width
        self.h = px_height
        self.font = font
        self.font_size = font_size
        self.speed = speed_rows_per_sec  # rows per second
        self.base = base
        self.tail_length = tail_length
        self.max_char_buffer = max_char_buffer

        # Head row in row units (not pixels), fractional for smooth movement
        self.head_row = random.uniform(-self.h // self.font_size, 0)
        # Collatz generator for this column
        self.collatz = collatz_generator(collatz_start)
        # Buffer of most recent characters (head at index 0)
        self.char_buffer = []
        # When head progresses by >=1.0 row, inject a new head character from next Collatz value
        self.row_accum = 0.0

        # Precompute x position in pixels
        self.x = self.x_index * self.font_size

    def _next_char_from_collatz(self) -> str:
        # From the next Collatz number, take a character derived from its base representation
        n = next(self.collatz)
        s = int_to_base(n, self.base)
        # Choose a "signal" character: last digit gives nice high-variance dynamics
        return s[-1]

    def update(self, dt: float):
        # Move head by speed * dt rows
        delta_rows = self.speed * dt
        self.head_row += delta_rows
        self.row_accum += delta_rows

        # For each new whole row advanced, append a new head character
        while self.row_accum >= 1.0:
            self.row_accum -= 1.0
            ch = self._next_char_from_collatz()
            self.char_buffer.insert(0, ch)
            # Cap buffer length
            if len(self.char_buffer) > self.max_char_buffer:
                self.char_buffer.pop()

        # Cull characters that have fully moved off-screen
        # Compute y of the last tail character; if beyond screen, drop from the end
        max_rows_on_screen = (self.h // self.font_size) + self.tail_length + 5
        if len(self.char_buffer) > max_rows_on_screen:
            self.char_buffer = self.char_buffer[:max_rows_on_screen]

    def draw(self, surface: pygame.Surface, head_color=(180, 255, 180), base_green=(0, 255, 65)):
        # Draw from head (index 0) downward; each successive character is farther behind the head
        # Compute y position in pixels for head
        head_y = int(self.head_row * self.font_size)

        for i, ch in enumerate(self.char_buffer):
            y = head_y - i * self.font_size
            if y < -self.font_size:
                # Above the visible area, skip
                continue
            if y > self.h:
                # Below the visible area, break early
                break

            # Color/alpha gradient for trail
            if i == 0:
                color = head_color
                alpha = 255
            else:
                # Decay both brightness and alpha with distance i
                # Exponential-like fade expressed via simple power curve
                decay = max(0.0, 1.0 - (i / self.tail_length)) if self.tail_length > 0 else 0.0
                decay = decay ** 1.5
                g = int(base_green[1] * (0.35 + 0.65 * decay))
                color = (0, g, int(base_green[2] * decay * 0.6))
                alpha = int(255 * decay)

            glyph = self.font.render(ch, True, color)
            glyph.set_alpha(alpha)
            surface.blit(glyph, (self.x, y))

# ---------------------------
# Main app
# ---------------------------

def main():
    parser = argparse.ArgumentParser(description="Collatz Matrix Rain (Pygame)")
    parser.add_argument("--width", type=int, default=1280, help="Window width in pixels")
    parser.add_argument("--height", type=int, default=720, help="Window height in pixels")
    parser.add_argument("--font-size", type=int, default=20, help="Font size in pixels")
    parser.add_argument("--columns", type=int, default=64, help="Number of columns")
    parser.add_argument("--speed", type=float, default=22.0, help="Rows per second per column")
    parser.add_argument("--base", type=int, default=36, help="Base for digit mapping (2..36)")
    parser.add_argument("--tail", type=int, default=30, help="Tail length in characters")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--start", type=str, default=None, help="Start integer for all columns (decimal), else random")
    parser.add_argument("--fps", type=int, default=60, help="Target FPS")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    pygame.init()
    pygame.display.set_caption("Collatz Matrix Rain")
    screen = pygame.display.set_mode((args.width, args.height), pygame.SRCALPHA)
    clock = pygame.time.Clock()

    # Font: attempt a monospace
    try:
        font = pygame.font.SysFont("Consolas,Menlo,Monaco,Courier New,monospace", args.font_size)
    except Exception:
        font = pygame.font.SysFont(None, args.font_size)

    # Compute grid columns aligned to font size
    cols_fit = args.width // args.font_size
    columns_count = min(args.columns, cols_fit)

    # Prepare starting seeds per column
    starts = []
    if args.start is not None:
        try:
            fixed = int(args.start, 10)
        except Exception:
            print("Invalid --start; must be a decimal integer", file=sys.stderr)
            return
        starts = [fixed for _ in range(columns_count)]
    else:
        for _ in range(columns_count):
            # Create large random starting numbers, mix even/odd
            n = random.getrandbits(256)
            if random.random() < 0.5:
                n |= 1
            starts.append(max(1, n))

    # Build columns across the width
    # Spread columns evenly over the available grid positions
    grid_indices = list(range(cols_fit))
    step = max(1, len(grid_indices) // max(1, columns_count))
    chosen_indices = grid_indices[::step][:columns_count]

    columns = []
    for i, x_idx in enumerate(chosen_indices):
        col = MatrixColumn(
            x_index=x_idx,
            px_width=args.width,
            px_height=args.height,
            font=font,
            collatz_start=starts[i],
            font_size=args.font_size,
            speed_rows_per_sec=args.speed * (0.8 + 0.4 * random.random()),  # small variance
            base=max(2, min(36, args.base)),
            tail_length=args.tail,
            max_char_buffer= (args.height // args.font_size) + args.tail + 10
        )
        columns.append(col)

    # Semi-transparent fade surface for trailing effect
    fade_surface = pygame.Surface((args.width, args.height), pygame.SRCALPHA)
    fade_surface.fill((0, 0, 0, 30))  # alpha controls trail persistence

    running = True
    while running:
        dt = clock.tick(args.fps) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Apply fade to create trails
        screen.blit(fade_surface, (0, 0))

        # Update and draw columns
        for col in columns:
            col.update(dt)
            col.draw(screen)

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
