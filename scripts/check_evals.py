"""Check a plugin-eval results record.

    uv run python scripts/check_evals.py RECORD.json
    uv run python scripts/check_evals.py --from-aggregate AGG.json --out RECORD.json

Prints one line per case (name, status, grader reasons). Exits non-zero when
the record is partial or counts a blocked case as a pass. Honest failures are
printed and are not by themselves a record error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.eval_pack import (  # noqa: E402
    EvalError,
    format_record,
    record_from_aggregate,
    record_problems,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", nargs="?", type=Path)
    parser.add_argument("--from-aggregate", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.from_aggregate is not None:
            if args.out is None:
                raise EvalError("--out is required with --from-aggregate")
            aggregate = json.loads(args.from_aggregate.read_text(encoding="utf-8"))
            record = record_from_aggregate(aggregate)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(
                json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        elif args.record is not None:
            record = json.loads(args.record.read_text(encoding="utf-8"))
        else:
            raise EvalError("pass a record path or --from-aggregate")
    except (OSError, json.JSONDecodeError, EvalError) as exc:
        print(f"eval record failed: {exc}", file=sys.stderr)
        return 1
    print(format_record(record))
    problems = record_problems(record)
    if problems:
        print("eval record refused:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
