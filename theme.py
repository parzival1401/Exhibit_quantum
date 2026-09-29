"""
theme.py — one colour scheme for all three screens.

The three windows sit side by side on a wall, so a background that
drifts from one to the next reads as three programs rather than one
exhibit. Every non-canvas surface takes its colour from here.

Canvases are deliberately absent: the colour field on Window 1 and the
gradient on Window 3 are the exhibit itself and paint themselves.
"""

# ── Backgrounds, darkest to lightest ─────────────────────────────────────────
# A deep blue-black rather than a neutral grey: it reads as "night sky"
# behind the colour work, and keeps the colours themselves the only
# saturated thing on the wall.
BG_DEEP    = '#06061a'   # the ground colour — welcome screens, page backing
BG_PAGE    = '#0d0d22'   # a page sitting on the ground (the gallery)
BG_PANEL   = '#111128'   # a panel sitting on a page (the colouring view)
BG_RAISED  = '#1a1a2e'   # cards, tiles and the scrollbar track
BG_BAR     = '#1e1e38'   # the bars pinned along the bottom of a screen

# Chrome that should recede: the staff menu bar and its drop-downs.
BG_MENU      = '#12121f'
BG_MENU_ITEM = '#252540'

# ── Text ─────────────────────────────────────────────────────────────────────
FG_BRIGHT  = '#ffffff'
FG_NORMAL  = '#ddddee'
FG_MUTED   = '#8888aa'   # hints, status lines, captions

# ── Lines and accents ────────────────────────────────────────────────────────
BORDER     = '#2a2a50'
ACCENT     = '#5a46cc'   # selection, focus, the quantum side
ACCENT_DIM = '#3a2e7a'

# Qt palette values, as RGB triples for QColor().
PALETTE_WINDOW      = (0x0d, 0x0d, 0x22)
PALETTE_BASE        = (0x06, 0x06, 0x1a)
PALETTE_ALT_BASE    = (0x1a, 0x1a, 0x2e)
PALETTE_BUTTON      = (0x1e, 0x1e, 0x38)
PALETTE_TEXT        = (0xdd, 0xdd, 0xee)
PALETTE_BRIGHT_TEXT = (0xff, 0xff, 0xff)
PALETTE_HIGHLIGHT   = (0x5a, 0x46, 0xcc)
PALETTE_TOOLTIP     = (0x1e, 0x1e, 0x38)


def page(background: str = BG_DEEP) -> str:
    """Stylesheet for a full-page widget."""
    return f'background-color: {background};'


def bottom_bar() -> str:
    """Stylesheet for a bar pinned along the bottom of a screen.

    Used by both side screens, which is what makes the channel lamps and
    the uncertainty meters read as the same piece of furniture.
    """
    return (f'background-color: {BG_BAR};'
            f'border-top: 1px solid {BORDER};')


def menu_bar() -> str:
    """Stylesheet for the staff menu bar and its drop-downs."""
    return f"""
        QMenuBar {{
            background-color : {BG_MENU};
            color            : {FG_MUTED};
            font-size        : 11px;
        }}
        QMenuBar::item:selected {{ background-color: {BG_MENU_ITEM}; }}
        QMenu {{
            background-color : {BG_MENU};
            color            : {FG_NORMAL};
            border           : 1px solid {BORDER};
        }}
        QMenu::item:selected {{ background-color: {ACCENT_DIM}; }}
        QMenu::separator     {{ height: 1px; background: {BORDER};
                                margin: 3px 0; }}
    """
