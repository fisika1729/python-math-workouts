#!/usr/bin/env python3
# Collatz Matrix Rain — Pygame
# Requirements: pygame (pip install pygame)

import sys
import random
import pygame

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
        tail_length: int = 30,
        max_char_buffer: int = 100
    ):
        self.x_index = x_index
        self.w = px_width
        self.h = px_height
        self.font = font
        self.font_size = font_size
        self.speed = speed_rows_per_sec  # rows per second
        self.tail_length = tail_length
        self.max_char_buffer = max_char_buffer

        # Head row in row units (not pixels), fractional for smooth movement
        self.head_row = random.uniform(-self.h // self.font_size, 0)
        # Collatz generator for this column
        self.collatz = collatz_generator(collatz_start)
        # Buffer of most recent numbers (head at index 0)
        self.char_buffer = []
        # When head progresses by >=1.0 row, inject a new head character from next Collatz value
        self.row_accum = 0.0

        # Precompute x position in pixels
        self.x = self.x_index * self.font_size

    def _next_char_from_collatz(self) -> str:
        # From the next Collatz number, return it as a string
        n = next(self.collatz)
        return str(n)

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
        max_rows_on_screen = (self.h // self.font_size) + self.tail_length + 5
        if len(self.char_buffer) > max_rows_on_screen:
            self.char_buffer = self.char_buffer[:max_rows_on_screen]

    def draw(self, surface: pygame.Surface, head_color=(180, 255, 180)):
        # Draw from head (index 0) downward; each successive number is farther behind the head
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
                decay = max(0.0, 1.0 - (i / self.tail_length)) if self.tail_length > 0 else 0.0
                decay = decay ** 1.5
                g = int(255 * (0.35 + 0.65 * decay))
                color = (0, g, int(255 * decay * 0.6))
                alpha = int(255 * decay)

            glyph = self.font.render(ch, True, color)
            glyph.set_alpha(alpha)
            surface.blit(glyph, (self.x, y))

# ---------------------------
# Main app
# ---------------------------

def main():
    pygame.init()
    pygame.display.set_caption("Collatz Matrix Rain")
    screen = pygame.display.set_mode((1280, 720), pygame.SRCALPHA)
    clock = pygame.time.Clock()

    # Font: attempt a monospace
    try:
        font = pygame.font.SysFont("Consolas,Menlo,Monaco,Courier New,monospace", 20)
    except Exception:
        font = pygame.font.SysFont(None, 20)

    # Compute grid columns aligned to font size
    cols_fit = 1280 // 20
    columns_count = 64

    # Prepare starting seeds per column
    starts = []
    for _ in range(columns_count):
        # Create large random starting numbers
        n = random.getrandbits(128)
        if random.random() < 0.5:
            n |= 1
        starts.append(max(1, n))

    # Build columns across the width
    grid_indices = list(range(cols_fit))
    step = max(1, len(grid_indices) // max(1, columns_count))
    chosen_indices = grid_indices[::step][:columns_count]

    columns = []
    for i, x_idx in enumerate(chosen_indices):
        col = MatrixColumn(
            x_index=x_idx,
            px_width=1280,
            px_height=720,
            font=font,
            collatz_start=starts[i],
            font_size=20,
            speed_rows_per_sec=22.0 * (0.8 + 0.4 * random.random()),  # small variance
            tail_length=30,
            max_char_buffer=(720 // 20) + 30 + 10
        )
        columns.append(col)

    # Semi-transparent fade surface for trailing effect
    fade_surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    fade_surface.fill((0, 0, 0, 30))  # alpha controls trail persistence

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

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
    try:
        main()
    except KeyboardInterrupt:
        print("\nMatrix rain interrupted by user.")
        pygame.quit()
