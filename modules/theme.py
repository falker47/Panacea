"""
Panacea Theme Module
Centralizes all design tokens: colors, fonts, spacing, and app metadata.
"""

APP_VERSION = "2.0"
APP_NAME = "Panacea System Optimizer"


class Colors:
    # Background layers
    BG_PRIMARY = "#1a1a1a"
    BG_CARD_BORDER = "#2a2a2a"
    BG_TERMINAL = "black"
    BG_STATUS = "#111111"

    # Sidebar tab colors (base, hover)
    DASH = ("#1F6AA5", "#144870")
    CLEAN = ("#C2185B", "#880E4F")
    DISK = ("#2da16f", "#1f7a52")
    TOOLS = ("#d65729", "#9e3f1d")
    APPS = ("#7b2cbf", "#521c85")
    TURBO = ("#00BCD4", "#00838F")
    RESURRECT_GOLD = "#FFD700"
    RESURRECT_HOVER = "#B8860B"

    # Semantic
    SUCCESS = "#4CAF50"
    WARNING = "#FFC107"
    ERROR = "#F44336"
    INFO = "#3B8ED0"
    TEXT_MUTED = "gray"
    TEXT_TERMINAL = "#00FF00"

    # Graph
    GRAPH_CPU = "#4CAF50"
    GRAPH_RAM = "#FFC107"
    GRAPH_GRID = "#2a2a2a"
    GRAPH_LABEL = "#444444"


class Fonts:
    LOGO = ("Segoe UI", 28, "bold")
    PAGE_TITLE = ("Segoe UI", 26, "bold")
    PAGE_SUBTITLE = ("Segoe UI", 12)
    CARD_TITLE = ("Segoe UI", 15, "bold")
    BODY = ("Segoe UI", 13)
    BODY_SMALL = ("Segoe UI", 11)
    TERMINAL = ("Consolas", 11)
    STAT_LARGE = ("Segoe UI", 20, "bold")
    STATUS_BAR = ("Segoe UI", 10)
    BUTTON = ("Segoe UI", 13)


class Spacing:
    PAGE_PAD_X = 24
    PAGE_PAD_Y = 20
    CARD_PAD = 12
    CARD_INTERNAL_PAD = 15
    CARD_CORNER_RADIUS = 12
    CARD_BORDER_WIDTH = 1
    SIDEBAR_WIDTH = 160
    SIDEBAR_BTN_HEIGHT = 38
    SIDEBAR_BTN_PAD_Y = 6


class Dimensions:
    WINDOW_WIDTH = 1100
    WINDOW_HEIGHT = 700
    MIN_WIDTH = 950
    MIN_HEIGHT = 600
    GRAPH_WIDTH = 350
    GRAPH_HEIGHT = 100
