"""Point a plugin copy at an operator-supplied HTTPS endpoint.

Does not start the eval runner and does not modify the repository plugin.
The shell wrapper ``scripts/eval_probe.sh`` is what invokes the runner.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import common  # noqa: E402
from scripts.eval_pack import (  # noqa: E402
    EvalError,
    retarget_plugin_copy,
    retarget_plugin_copy_local,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--copy", required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url")
    group.add_argument("--port", type=int)
    args = parser.parse_args(argv)
    try:
        if args.port is not None:
            retarget_plugin_copy_local(
                args.copy, args.port, repo_plugin=common.plugin_dir()
            )
        else:
            retarget_plugin_copy(args.copy, args.url, repo_plugin=common.plugin_dir())
    except EvalError as exc:
        print(f"probe setup failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
