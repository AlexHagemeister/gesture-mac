"""Entry point: `uv run gesture-mac` or `python -m gesture_mac.app`."""
from .menubar import run


def main() -> None:
    run()


if __name__ == "__main__":
    main()
