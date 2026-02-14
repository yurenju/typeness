import argparse

from typeness.main import main


def cli():
    """CLI entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        prog="typeness",
        description="Local voice input tool — speech to structured text",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="save each recording as WAV + JSON to the debug/ directory",
    )
    args = parser.parse_args()
    main(debug=args.debug)


if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        print("\nBye!")
