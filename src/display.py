RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
WHITE = "\033[97m"
BG_BLUE = "\033[44m"


def c(text: str, *codes: str) -> str:
    return "".join(codes) + str(text) + RESET


def header(title: str, width: int = 60) -> None:
    border = c("\u2550" * width, CYAN)
    print(f"\n{border}")
    print(c(f"  {title.center(width - 2)}  ", BOLD, WHITE, BG_BLUE))
    print(border)


def sep(width: int = 60) -> None:
    print(c("\u2500" * width, DIM))


def stat(label: str, value: str, color: str = WHITE) -> None:
    print(f"  {c(label + ' :', DIM):.<40} {c(value, color, BOLD)}")