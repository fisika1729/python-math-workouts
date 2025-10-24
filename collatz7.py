#!/usr/bin/env python3
# Collatz Vertical Rain — Matrix look with glow, random columns, per-digit bottom culling

import sys, argparse, random, pygame

# ---------- Collatz (strict integer math) ----------
def collatz_step(n: int) -> int:
    return n // 2 if n % 2 == 0 else 3 * n + 1  # exact even/odd rule on Python ints [web:9]

# ---------- Column allocator with cooldown (avoid repeats) ----------
class ColumnAllocator:
    def __init__(self, cols_fit: int, cooldown_ms: int):
        self.cols_fit = max(1, cols_fit)
        self.cooldown_ms = max(0, cooldown_ms)
        self.last_used = [-10_000_000] * self.cols_fit

    def pick(self, now_ms: int, avoid: int | None = None) -> int:
        candidates = []
        for c in range(self.cols_fit):
            if avoid is not None and c == avoid:
                continue
            if now_ms - self.last_used[c] >= self.cooldown_ms:
                candidates.append(c)
        if candidates:
            choice = random.choice(candidates)
        else:
            # fallback to least-recently-used
            choice = max(range(self.cols_fit), key=lambda c: now_ms - self.last_used[c])
        self.last_used[choice] = now_ms
        return choice

# ---------- Small radial glow sprites (for additive bloom) ----------
def make_glow(radius: int, color=(80, 255, 100), steps=5) -> pygame.Surface:
    # Concentric circles decreasing alpha to mimic a gaussian-ish blob [web:70][web:143]
    surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for i in range(steps, 0, -1):
        r = int(radius * i / steps)
        a = int(180 * (i / steps) ** 2)
        pygame.draw.circle(surf, (*color, a), (radius, radius), r)
    return surf.convert_alpha()  # fast alpha blits [web:70][web:150]

# ---------- One vertical stream (one integer's digits) ----------
class VerticalNumberStream:
    """
    - Emits one integer's decimal digits vertically down a fixed column (one digit per row step).
    - Brightness increases with y; head gets an additive glow; tail digits cull individually at bottom.
    - Spawns the next Collatz value once the head reaches halfway down the screen.
    """
    def __init__(self, value: int, column: int, cols_fit: int, row_px: int, screen_h: int,
                 rows_per_sec: float, digit_gap_rows: int, log_starts: bool,
                 glow_small: pygame.Surface, glow_big: pygame.Surface, label: str = ""):
        self.value = value
        self.digits = list(str(value))  # render-only; math uses integer state [web:9]
        self.column = max(0, min(column, cols_fit - 1))
        self.row_px = row_px
        self.screen_h = screen_h
        self.rows_per_sec = rows_per_sec
        self.digit_gap_rows = max(0, digit_gap_rows)
        self.log_starts = log_starts
        self.glow_small = glow_small
        self.glow_big = glow_big

        # Emission state
        self.head_row = -2.0
        self.row_accum = 0.0
        self.rows_until_next_digit = 0
        self.emit_index = 0
        self.done_emitting = False
        self.spawned_next = False

        # Head-at-index-0 buffer
        self.char_buffer: list[str] = []

        if self.log_starts:
            print(f"{label}start: {self.value}", flush=True)

    def update(self, dt: float):
        delta_rows = self.rows_per_sec * dt
        self.head_row += delta_rows
        self.row_accum += delta_rows

        # Emit one digit per whole row advanced
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

        # Per-digit bottom culling (shorten stack gradually)
        if self.char_buffer:
            tail_idx = len(self.char_buffer) - 1
            tail_y = int(self.head_row * self.row_px) - tail_idx * self.row_px
            if tail_y >= self.screen_h - 1:
                self.char_buffer.pop()

    def should_spawn_next(self) -> bool:
        return int(self.head_row * self.row_px) >= (self.screen_h // 2)  # halfway trigger [web:60]

    def offscreen(self) -> bool:
        return self.done_emitting and not self.char_buffer  # only after all digits fell off [web:60]

    def draw(self, surface: pygame.Surface, font: pygame.font.Font,
             head_rgb=(220, 255, 220), base_green=(0, 255, 65), height_px: int = 1080):
        def brightness(y_px: int) -> float:
            t = max(0.0, min(1.0, y_px / height_px))
            return 0.35 + 0.65 * (t ** 1.2)  # smooth ramp toward bottom [web:70]

        head_y = int(self.head_row * self.row_px)
        x_px = self.column * self.row_px
        cx = x_px + self.row_px // 2

        for i, ch in enumerate(self.char_buffer):
            y_px = head_y - i * self.row_px
            if y_px < -self.row_px or y_px > self.screen_h:
                continue

            m = brightness(y_px)
            # Additive glow: strong on head, subtle on tail [web:143][web:70]
            if i == 0:
                g = self.glow_big.copy()
                g.set_alpha(int(160 * m))
                surface.blit(g, g.get_rect(center=(cx, y_px + self.row_px // 2)), special_flags=pygame.BLEND_ADD)
            else:
                g = self.glow_small.copy()
                g.set_alpha(int(90 * m))
                surface.blit(g, g.get_rect(center=(cx, y_px + self.row_px // 2)), special_flags=pygame.BLEND_ADD)

            # Glyph color/alpha
            r = int(head_rgb[0] * m * 0.8)
            gcol = int(base_green[1] * m)
            b = int(base_green[2] * m * 0.5)
            a = int(255 * m)

            glyph = font.render(ch, True, (r, gcol, b))  # antialiased text for crisp digits [web:78]
            glyph.set_alpha(a)
            surface.blit(glyph, (x_px, y_px))  # normal alpha blend under the additive halo [web:70]

# ---------- App ----------
class CollatzVerticalRain:
    def __init__(self, args):
        self.args = args
        pygame.init()
        pygame.display.set_caption("Collatz Vertical Rain — Matrix glow")
        self.screen = pygame.display.set_mode((args.width, args.height), pygame.SRCALPHA)
        self.clock = pygame.time.Clock()  # stable dt pacing [web:60]

        # Monospace font (no shadow)
        try:
            self.font = pygame.font.SysFont("Consolas,Menlo,Monaco,Courier New,monospace", args.font_size)
        except Exception:
            self.font = pygame.font.SysFont(None, args.font_size)  # fallback [web:78]

        self.row_px = args.font_size
        self.cols_fit = max(1, args.width // self.row_px)

        # Trail fade for the classic rain
        self.fade_surface = pygame.Surface((args.width, args.height), pygame.SRCALPHA)
        self.fade_surface.fill((0, 0, 0, max(0, min(255, args.trail_alpha))))  # persistent tails [web:70]

        # Prebuilt small/large glow sprites (converted for fast alpha blits)
        self.glow_small = make_glow(int(self.row_px * 0.7)).convert_alpha()  # preconvert for speed [web:70][web:150]
        self.glow_big = make_glow(int(self.row_px * 1.2)).convert_alpha()    # slightly larger head halo [web:70][web:150]

        self.alloc = ColumnAllocator(self.cols_fit, args.column_cooldown_ms)  # random columns with cooldown [web:60]
        self.streams: list[VerticalNumberStream] = []

        # Seed one stream per column to avoid blanks at start (columns assigned by allocator)
        now_ms = pygame.time.get_ticks()
        for _ in range(self.cols_fit):
            col = self.alloc.pick(now_ms)
            self.streams.append(self._new_seed_stream(col, label="Seed "))

        # Target concurrency for dense fill
        self.target_active = max(self.cols_fit, int(self.cols_fit * args.density))  # density × columns [web:60]

    def _seed_value(self) -> int:
        if self.args.start is not None:
            return max(1, int(self.args.start, 10))  # fixed big seed if provided [web:9]
        dmin = max(10, self.args.min_digits)
        dmax = max(dmin, self.args.max_digits)
        k = random.randint(dmin, dmax)
        lo, hi = 10 ** (k - 1), 10 ** k - 1
        return random.randrange(lo, hi + 1)  # random big integer seed [web:9]

    def _new_seed_stream(self, col: int, label=""):
        return VerticalNumberStream(
            value=self._seed_value(),
            column=col,
            cols_fit=self.cols_fit,
            row_px=self.row_px,
            screen_h=self.args.height,
            rows_per_sec=self.args.speed,
            digit_gap_rows=self.args.digit_gap_rows,
            log_starts=self.args.log_starts,
            glow_small=self.glow_small,
            glow_big=self.glow_big,
            label=label,
        )

    def _spawn_next_from(self, parent: VerticalNumberStream):
        nxt = collatz_step(parent.value)  # strict integer step [web:9]
        now_ms = pygame.time.get_ticks()
        col = self.alloc.pick(now_ms, avoid=parent.column)  # prefer a different column [web:60]
        self.streams.append(
            VerticalNumberStream(
                value=nxt,
                column=col,
                cols_fit=self.cols_fit,
                row_px=self.row_px,
                screen_h=self.args.height,
                rows_per_sec=self.args.speed,
                digit_gap_rows=self.args.digit_gap_rows,
                log_starts=self.args.log_starts,
                glow_small=self.glow_small,
                glow_big=self.glow_big,
                label="Next ",
            )
        )

    def _top_up_density(self):
        deficit = self.target_active - len(self.streams)
        now_ms = pygame.time.get_ticks()
        for _ in range(max(0, deficit)):
            col = self.alloc.pick(now_ms)
            self.streams.append(self._new_seed_stream(col, label="Seed "))

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(self.args.fps) / 1000.0  # consistent speed across machines [web:60]
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            # Global fade pass for trails
            self.screen.blit(self.fade_surface, (0, 0))  # leaves a soft tail behind digits [web:70]

            # Update streams and spawn next numbers at mid-screen
            for s in list(self.streams):
                s.update(dt)
                if not s.spawned_next and s.should_spawn_next():
                    s.spawned_next = True
                    self._spawn_next_from(s)

            # Remove only streams that finished and lost all digits
            self.streams = [s for s in self.streams if not s.offscreen()]  # column won’t pop instantly [web:60]

            # Keep the screen densely filled
            self._top_up_density()  # avoids intermittent blank columns [web:60]

            # Draw
            for s in self.streams:
                s.draw(self.screen, self.font, height_px=self.args.height)  # glow + glyph per digit [web:70]

            pygame.display.flip()

        pygame.quit()

def main():
    parser = argparse.ArgumentParser(description="Collatz vertical Matrix rain with glow")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--font-size", type=int, default=18, help="Cell size / digit height")
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--speed", type=float, default=8.0, help="Rows per second (lower = slower)")
    parser.add_argument("--trail-alpha", type=int, default=50, help="Screen fade alpha per frame (0..255)")
    parser.add_argument("--digit-gap-rows", type=int, default=0, help="Blank rows between digits")
    parser.add_argument("--density", type=float, default=1.6, help="Target streams = density × columns")
    parser.add_argument("--column-cooldown-ms", type=int, default=800, help="Min ms before reusing a column")
    parser.add_argument("--min-digits", type=int, default=10)
    parser.add_argument("--max-digits", type=int, default=26)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--start", type=str, default=None, help="Optional fixed starting integer (>=10 digits)")
    parser.add_argument("--log-starts", action="store_true", help="Print stream starts to terminal")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    CollatzVerticalRain(args).run()

if __name__ == "__main__":
    main()
