import sys
import kosmorph.modules  # noqa: F401  # Ensure all actions register at startup
from kosmorph.core.plugins import load_external_plugins
from kosmorph.cli.commands import run_cli


def main() -> None:
    load_external_plugins()
    sys.exit(run_cli())


if __name__ == "__main__":
    main()
