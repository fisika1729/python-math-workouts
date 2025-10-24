#!/usr/bin/env python3
# Collatz Threaded Matrix Rain — start-at-top, spawn-next-after-5, top-culling, non-spam columns

import sys, argparse, random, pygame

# ---------- Collatz (strict integer math) ----------
def collatz_step(n: int) -> int:
    # Even -> n/2, Odd -> 3n+1, exact on Python ints
    return n // 2 if n % 2 == 0 else 3 * n + 1  # [web:9]

# ---------- Column allocator with cooldown (avoid spawning same lane repeatedly) ----------
class ColumnAllocator:
    def __init__(self, cols_fit: int, cooldown_ms: int):
        self.cols_fit = max(1, cols_fit)
        self.cooldown_ms = max(0, cooldown_ms)
        self.last_used = [-10_000_000] * self.cols_fit

    def pick(self, now_ms: int, avoid: int | None = None) -> int:
        choices = []
        for c in range(self.cols_fit):
            if avoid is not None and c == avoid:
                continue
            if now_ms - self.last_used[c] >= self.cooldown_ms:
                choices.append(c)
        if choices:
            col = random.choice(choices)
        else:
            # fallback to least-recently-used
            col = max(range(self.cols_fit), key=lambda c: now_ms - self.last_used[c])
        self.last_used[col] = now_ms
        return col  # [web:60]

# ---------- One “thread” (digits of a single integer) ----------
class ThreadStream:
    """
    - Starts at top row (y=0) in a fixed column; emits one digit per row step down that column.
    - After trigger_emits digits, requests spawning the next Collatz value in a new random column.
    - Oldest digits are culled when they scroll above the top, so disappearance mirrors appearance.
    """
    def __init__(self, value: int, column: int, cols_fit: int, row_px: int, screen_h: int,
                 rows_per_sec: float, digit_gap_rows: int, trigger_emits: int, log_starts: bool):
        self.value = value
        self.digits = list(str(value))          # render-only
        self.column = max(0, min(column, cols_fit - 1))
        self.row_px = row_px
        self.screen_h = screen_h
        self.rows_per_sec = rows_per_sec
        self.digit_gap_rows = max(0, digit_gap_rows)
        self.trigger_emits = max(1, trigger_emits)
        self.log_starts = log_starts

        # Emission state (start exactly at top)
        self.head_row = 0.0                     # top row
        self.row_accum = 1.0                    # emit immediately on first update
        self.rows_until_next_digit = 0
        self.emit_index = 0
        self.emitted_total = 0
        self.done_emitting = False
        self.spawned_next = False

        # Visible stack: newest at index 0 (head)
        self.char_buffer: list[str] = []

        if self.log_starts:
            print(f"start: {self.value}", flush=True)

    def update(self, dt: float):
        # Move head and accumulate row progress
        delta_rows = self.rows_per_sec * dt
        self.head_row += delta_rows
        self.row_accum += delta_rows

        # Emit one digit for each whole row advanced
        while self.row_accum >= 1.0 and not self.done_emitting:
            self.row_accum -= 1.0
            if self.rows_until_next_digit <= 0:
                if self.emit_index < len(self.digits):
                    self.char_buffer.insert(0, self.digits[self.emit_index])
                    self.emit_index += 1
                    self.emitted_total += 1
                    self.rows_until_next_digit = 1 + self.digit_gap_rows
                else:
                    self.done_emitting = True
            else:
                self.rows_until_next_digit -= 1

        # Top culling: remove oldest digits once they scroll above the top
        while self.char_buffer:
            tail_idx = len(self.char_buffer) - 1
            tail_y_px = int(self.head_row * self.row_px) - tail_idx * self.row_px
            if tail_y_px < -self.row_px:
                self.char_buffer.pop()
            else:
                break  # [web:70]

    def wants_next_spawn(self) -> bool:
        # Ask to spawn the next Collatz value after exactly N emitted digits
        return (not self.spawned_next) and (self.emitted_total >= self.trigger_emits)  # [web:9]

    def mark_spawned(self):
        self.spawned_next = True  # [web:60]

    def offscreen(self) -> bool:
        # Stream ends only when all digits have been emitted and buffer is empty
        return self.done_emitting and not self.char_buffer  # [web:60]

    def draw(self, surface: pygame.Surface, font: pygame.font.Font,
             head_rgb=(220, 255, 220), base_green=(0, 255, 65), height_px: int = 1080):
        # Brightness grows with y; max near bottom for a neon look
        def brightness(y_px: int) -> float:
            t = max(0.0, min(1.0, y_px / height_px))
            return 0.35 + 0.65 * (t ** 1.2)  # [web:70]

        head_y = int(self.head_row * self.row_px)
        x_px = self.column * self.row_px

        for i, ch in enumerate(self.char_buffer):
            y_px = head_y - i * self.row_px
            if y_px < -self.row_px or y_px > self.screen_h:
                continue
            m = brightness(y_px)
            r = int(head_rgb[0] * m * 0.8)
            g = int(base_green[1] * m)
            b = int(base_green[2] * m * 0.5)
            a = int(255 * m)
            glyph = font.render(ch, True, (r, g, b))  # antialiased digits for clarity
            glyph.set_alpha(a)
            surface.blit(glyph, (x_px, y_px))  # standard alpha over faded background [web:78][web:70]

# ---------- App orchestrating staggered threads ----------
class CollatzThreadedRain:
    def __init__(self, args):
        self.args = args
        pygame.init()
        pygame.display.set_caption("Collatz Threaded Rain — staggered 5-digit spawns")
        self.screen = pygame.display.set_mode((args.width, args.height), pygame.SRCALPHA)
        self.clock = pygame.time.Clock()  # delta-time pacing [web:60]

        # Monospace font, no shadow
        try:
            self.font = pygame.font.SysFont("Consolas,Menlo,Monaco,Courier New,monospace", args.font_size)
        except Exception:
            self.font = pygame.font.SysFont(None, args.font_size)  # [web:78]

        self.row_px = args.font_size
        self.cols_fit = max(1, args.width // self.row_px)

        # Trail fade (global) for smooth tails
        self.fade_surface = pygame.Surface((args.width, args.height), pygame.SRCALPHA)
        self.fade_surface.fill((0, 0, 0, max(0, min(255, args.trail_alpha))))  # [web:70]

        self.alloc = ColumnAllocator(self.cols_fit, args.column_cooldown_ms)
        self.streams: list[ThreadStream] = []

        # Seed exactly one thread to start the chain cleanly (not spamming every column)
        col0 = self.alloc.pick(pygame.time.get_ticks())
        self.streams.append(self._new_thread(self._seed_value(), col0))  # [web:60]

        # Optional minimal background fill: keep at least min_concurrent threads active
        self.min_concurrent = max(1, args.min_concurrent)

    def _seed_value(self) -> int:
        if self.args.start is not None:
            return max(1, int(self.args.start, 10))
        dmin = max(10, self.args.min_digits)
        dmax = max(dmin, self.args.max_digits)
        k = random.randint(dmin, dmax)
        lo, hi = 10 ** (k - 1), 10 ** k - 1
        return random.randrange(lo, hi + 1)  # [web:9]

    def _new_thread(self, value: int, column: int) -> ThreadStream:
        return ThreadStream(
            value=value,
            column=column,
            cols_fit=self.cols_fit,
            row_px=self.row_px,
            screen_h=self.args.height,
            rows_per_sec=self.args.speed,
            digit_gap_rows=self.args.digit_gap_rows,
            trigger_emits=self.args.spawn_after_digits,
            log_starts=self.args.log_starts,
        )  # [web:60]

    def _spawn_next_from(self, parent: ThreadStream):
        nxt = collatz_step(parent.value)
        now_ms = pygame.time.get_ticks()
        col = self.alloc.pick(now_ms, avoid=parent.column)
        self.streams.append(self._new_thread(nxt, col))
        parent.mark_spawned()  # [web:9][web:60]

    def _top_up_min_concurrent(self):
        # Keep a gentle baseline so the screen never goes empty, but avoid spam
        while len(self.streams) < self.min_concurrent:
            col = self.alloc.pick(pygame.time.get_ticks())
            self.streams.append(self._new_thread(self._seed_value(), col))  # [web:60]

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(self.args.fps) / 1000.0  # consistent motion [web:60]
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            # Fade trails
            self.screen.blit(self.fade_surface, (0, 0))  # [web:70]

            # Update all threads
            for s in list(self.streams):
                s.update(dt)
                # spawn next Collatz thread exactly after N emitted digits
                if s.wants_next_spawn():
                    self._spawn_next_from(s)

            # Remove finished threads (after their digits scrolled off the top)
            self.streams = [s for s in self.streams if not s.offscreen()]  # [web:60]

            # Maintain minimal concurrency (no blank screen), but not dense spam
            self._top_up_min_concurrent()  # [web:60]

            # Draw
            for s in self.streams:
                s.draw(self.screen, self.font, height_px=self.args.height)  # [web:70][web:78]

            pygame.display.flip()

        pygame.quit()

def main():
    parser = argparse.ArgumentParser(description="Collatz threaded rain — spawn after 5 digits, top-cull")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--font-size", type=int, default=18)
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--speed", type=float, default=8.0, help="Rows per second; lower = slower")
    parser.add_argument("--trail-alpha", type=int, default=50, help="Global trail fade alpha per frame (0..255)")
    parser.add_argument("--digit-gap-rows", type=int, default=0, help="Extra blank rows between emitted digits")
    parser.add_argument("--spawn-after-digits", type=int, default=5, help="Start next thread after this many digits")
    parser.add_argument("--column-cooldown-ms", type=int, default=900, help="Min ms before reusing same column")
    parser.add_argument("--min-concurrent", type=int, default=6, help="Baseline number of concurrent threads")
    parser.add_argument("--min-digits", type=int, default=10)
    parser.add_argument("--max-digits", type=int, default=26)
    parser.add_argument("--start", type=str, default=None, help="Optional fixed starting integer (>=10 digits)")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--log-starts", action="store_true")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    CollatzThreadedRain(args).run()

if __name__ == "__main__":
    main()
