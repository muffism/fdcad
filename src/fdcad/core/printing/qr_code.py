"""QR code patterns for printed tags (TR311, DECISIONS D1215).

A plain implementation of the public QR code standard (ISO/IEC 18004): byte mode,
error correction level M, versions 1 to 10 (up to 213 bytes of UTF-8 text), with
the mask chosen by the standard's penalty rules. ``modules`` gives the grid of
dark (True) and light modules; ``outline`` turns the dark modules into the closed
outlines of one joined region, for a sketch. No Qt, no kernel.
"""

from __future__ import annotations

#: Data codewords, error correction codewords per block and blocks, for level M.
_DATA = (0, 16, 28, 44, 64, 86, 108, 124, 154, 182, 216)
_ECC = (0, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26)
_BLOCKS = (0, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5)
_REMAINDER = (0, 0, 7, 7, 7, 7, 7, 0, 0, 0, 0)
MAX_VERSION = 10
#: Level M's two format bits.
_LEVEL_M = 0


def _gf_tables() -> tuple[list[int], list[int]]:
    exp = [0] * 512
    log = [0] * 256
    x = 1
    for i in range(255):
        exp[i] = x
        log[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        exp[i] = exp[i - 255]
    return exp, log


_EXP, _LOG = _gf_tables()


def _mul(a: int, b: int) -> int:
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _generator(degree: int) -> list[int]:
    poly = [1]
    for i in range(degree):
        nxt = [0] * (len(poly) + 1)
        for j, c in enumerate(poly):
            nxt[j] ^= c
            nxt[j + 1] ^= _mul(c, _EXP[i])
        poly = nxt
    return poly


def ecc(data: list[int], degree: int) -> list[int]:
    """Reed-Solomon error correction codewords of ``data``."""
    gen = _generator(degree)
    rest = list(data) + [0] * degree
    for i in range(len(data)):
        c = rest[i]
        if c:
            for j in range(1, len(gen)):
                rest[i + j] ^= _mul(gen[j], c)
    return rest[len(data) :]


def version_for(length: int) -> int:
    """The smallest version that holds ``length`` bytes. Raises ValueError."""
    for v in range(1, MAX_VERSION + 1):
        count_bits = 8 if v < 10 else 16
        if 4 + count_bits + 8 * length <= 8 * _DATA[v]:
            return v
    raise ValueError(f"the text is longer than {capacity()} bytes")


def capacity() -> int:
    """The most bytes a code tag holds."""
    return (8 * _DATA[MAX_VERSION] - 4 - 16) // 8


def _codewords(data: bytes, v: int) -> list[int]:
    bits: list[int] = []

    def put(value: int, count: int) -> None:
        bits.extend((value >> (count - 1 - i)) & 1 for i in range(count))

    put(0b0100, 4)
    put(len(data), 8 if v < 10 else 16)
    for b in data:
        put(b, 8)
    room = 8 * _DATA[v]
    put(0, min(4, room - len(bits)))
    put(0, (-len(bits)) % 8)
    words = [int("".join(map(str, bits[i : i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = 0xEC
    while len(words) < _DATA[v]:
        words.append(pad)
        pad ^= 0xEC ^ 0x11
    # Blocks: the short ones first, the long ones have one more data codeword.
    blocks, degree = _BLOCKS[v], _ECC[v]
    short = _DATA[v] // blocks
    longs = _DATA[v] % blocks
    parts, start = [], 0
    for k in range(blocks):
        size = short + (1 if k >= blocks - longs else 0)
        parts.append(words[start : start + size])
        start += size
    eccs = [ecc(p, degree) for p in parts]
    out = []
    for i in range(short + 1):
        out += [p[i] for p in parts if i < len(p)]
    for i in range(degree):
        out += [e[i] for e in eccs]
    return out


def _alignment(v: int) -> list[int]:
    if v == 1:
        return []
    count = v // 7 + 2
    size = 17 + 4 * v
    step = (v * 4 + count * 2 + 1) // (count * 2 - 2) * 2
    return [6, *sorted(size - 7 - i * step for i in range(count - 1))]


def _bch(value: int, poly: int, bits: int) -> int:
    rest = value << bits
    top = poly.bit_length() - 1
    for i in range(rest.bit_length() - 1, top - 1, -1):
        if rest >> i & 1:
            rest ^= poly << (i - top)
    return (value << bits) | rest


def _format_bits(mask: int) -> int:
    return _bch((_LEVEL_M << 3) | mask, 0b10100110111, 10) ^ 0b101010000010010


def _mask(m: int, r: int, c: int) -> bool:
    return (
        (r + c) % 2 == 0,
        r % 2 == 0,
        c % 3 == 0,
        (r + c) % 3 == 0,
        (r // 2 + c // 3) % 2 == 0,
        r * c % 2 + r * c % 3 == 0,
        (r * c % 2 + r * c % 3) % 2 == 0,
        ((r + c) % 2 + r * c % 3) % 2 == 0,
    )[m]


def _base(v: int) -> tuple[list[list[bool]], list[list[bool]]]:
    """The fixed patterns and which modules they take."""
    n = 17 + 4 * v
    grid = [[False] * n for _ in range(n)]
    used = [[False] * n for _ in range(n)]

    def set_(r: int, c: int, dark: bool) -> None:
        if 0 <= r < n and 0 <= c < n:
            grid[r][c] = dark
            used[r][c] = True

    for r0, c0 in ((0, 0), (0, n - 7), (n - 7, 0)):
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                ring = max(abs(dr - 3), abs(dc - 3))
                set_(r0 + dr, c0 + dc, ring != 2 and ring != 4 and ring <= 3)
    for i in range(8, n - 8):
        set_(6, i, i % 2 == 0)
        set_(i, 6, i % 2 == 0)
    centres = _alignment(v)
    last = len(centres) - 1
    for i, r in enumerate(centres):
        for j, c in enumerate(centres):
            if (i, j) in ((0, 0), (0, last), (last, 0)):
                continue  # under a finder pattern
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    set_(r + dr, c + dc, max(abs(dr), abs(dc)) != 1)
    for i in range(9):  # room for the format bits
        for r, c in ((8, i), (i, 8)):
            used[r][c] = True
    for i in range(8):
        used[8][n - 1 - i] = True
        used[n - 1 - i][8] = True
    set_(n - 8, 8, True)  # the dark module
    if v >= 7:
        info = _bch(v, 0b1111100100101, 12)
        for i in range(18):
            dark = bool(info >> i & 1)
            set_(n - 11 + i % 3, i // 3, dark)
            set_(i // 3, n - 11 + i % 3, dark)
    return grid, used


def _place(grid: list[list[bool]], used: list[list[bool]], words: list[int], extra: int) -> None:
    n = len(grid)
    bits = [w >> (7 - i) & 1 for w in words for i in range(8)] + [0] * extra
    k = 0
    col = n - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(n - 1, -1, -1) if upward else range(n)
        for r in rows:
            for c in (col, col - 1):
                if not used[r][c]:
                    grid[r][c] = bool(bits[k]) if k < len(bits) else False
                    k += 1
        upward = not upward
        col -= 2


def _format(grid: list[list[bool]], mask: int) -> None:
    n = len(grid)
    bits = _format_bits(mask)
    for i in range(15):
        dark = bool(bits >> i & 1)
        # Around the top left finder.
        if i < 6:
            grid[i][8] = dark
        elif i < 8:
            grid[i + 1][8] = dark
        else:
            grid[8][14 - i if i > 8 else 7] = dark
        # Split between the other two finders.
        if i < 8:
            grid[8][n - 1 - i] = dark
        else:
            grid[n - 15 + i][8] = dark
    grid[n - 8][8] = True


def _penalty(g: list[list[bool]]) -> int:
    n = len(g)
    score = 0
    for lines in (g, [list(col) for col in zip(*g, strict=True)]):
        for line in lines:
            run = 1
            for i in range(1, n + 1):
                if i < n and line[i] == line[i - 1]:
                    run += 1
                    continue
                if run >= 5:
                    score += run - 2
                run = 1
            text = "".join("1" if x else "0" for x in line)
            score += 40 * (text.count("10111010000") + text.count("00001011101"))
    for r in range(n - 1):
        for c in range(n - 1):
            if g[r][c] == g[r][c + 1] == g[r + 1][c] == g[r + 1][c + 1]:
                score += 3
    dark = sum(map(sum, g))
    score += 10 * (abs(dark * 20 - n * n * 10) // (n * n))
    return score


def modules(text: str) -> list[list[bool]]:
    """The QR code of ``text`` (UTF-8) as rows of dark (True) and light modules, without
    the quiet zone. Raises ValueError for text longer than :func:`capacity`."""
    data = text.encode("utf-8")
    v = version_for(len(data))
    words = _codewords(data, v)
    best: list[list[bool]] | None = None
    best_score = 0
    for m in range(8):
        grid, used = _base(v)
        _place(grid, used, words, _REMAINDER[v])
        n = len(grid)
        for r in range(n):
            for c in range(n):
                if not used[r][c] and _mask(m, r, c):
                    grid[r][c] = not grid[r][c]
        _format(grid, m)
        score = _penalty(grid)
        if best is None or score < best_score:
            best, best_score = grid, score
    assert best is not None
    return best


Point = tuple[int, int]
#: Where two dark modules touch only at a corner, each outline cuts the corner back
#: by this share of a module, so no two outlines share a point (a sketch needs each
#: point to join exactly two curves).
CORNER_CUT = 0.04


def outline(grid: list[list[bool]]) -> list[list[tuple[float, float]]]:
    """The closed outlines of the dark modules, in module units (x right, y up, the
    bottom left corner at 0, 0): outer loops anticlockwise, holes clockwise. Straight
    runs are merged. Modules that touch only at a corner are kept apart: each loop is
    walked with the dark area on its left, and cut back at such corners by
    :data:`CORNER_CUT`."""
    n = len(grid)

    def dark(r: int, c: int) -> bool:
        return 0 <= r < n and 0 <= c < n and grid[r][c]

    # Edges with dark on the left, between lattice points (x, y); row r is y = n - 1 - r.
    nxt: dict[Point, list[Point]] = {}
    for r in range(n):
        for c in range(n):
            if not grid[r][c]:
                continue
            x, y = c, n - 1 - r
            if not dark(r + 1, c):
                nxt.setdefault((x, y), []).append((x + 1, y))  # bottom, going right
            if not dark(r, c + 1):
                nxt.setdefault((x + 1, y), []).append((x + 1, y + 1))  # right, going up
            if not dark(r - 1, c):
                nxt.setdefault((x + 1, y + 1), []).append((x, y + 1))  # top, going left
            if not dark(r, c - 1):
                nxt.setdefault((x, y + 1), []).append((x, y))  # left, going down
    touches = {p for p, outs in nxt.items() if len(outs) > 1}
    loops: list[list[tuple[float, float]]] = []
    while nxt:
        start = next(iter(nxt))
        loop = [start]
        here, came = start, None
        while True:
            options = nxt[here]
            if len(options) == 1 or came is None:
                go = options[0]
            else:
                # Two ways out at a corner touch: turn left, keeping modules apart.
                dx, dy = here[0] - came[0], here[1] - came[1]
                left = (here[0] - dy, here[1] + dx)
                go = left if left in options else options[0]
            options.remove(go)
            if not options:
                del nxt[here]
            came, here = here, go
            if here == start:
                break
            loop.append(here)
        loops.append(_cut_corners(_merge(loop), touches))
    return loops


def _cut_corners(loop: list[Point], touches: set[Point]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    m = len(loop)
    for i, p in enumerate(loop):
        if p not in touches:
            out.append((float(p[0]), float(p[1])))
            continue
        a, b = loop[i - 1], loop[(i + 1) % m]
        out += [_toward(p, a), _toward(p, b)]
    return out


def _toward(p: Point, q: Point) -> tuple[float, float]:
    """The point :data:`CORNER_CUT` of a module from ``p`` toward ``q``."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    length = max(abs(dx), abs(dy))
    return (p[0] + CORNER_CUT * dx / length, p[1] + CORNER_CUT * dy / length)


def _merge(loop: list[Point]) -> list[Point]:
    """Drop the points in the middle of straight runs."""
    out = []
    m = len(loop)
    for i, p in enumerate(loop):
        a, b = loop[i - 1], loop[(i + 1) % m]
        if (p[0] - a[0]) * (b[1] - p[1]) - (p[1] - a[1]) * (b[0] - p[0]) != 0:
            out.append(p)
    return out
