"""Read-only CLI preview for experiment specifications."""

import argparse

from runner.spec import SpecError, load_specs


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and preview an AUC JSONL experiment batch")
    parser.add_argument("spec", help="Path to JSONL batch")
    args = parser.parse_args()
    try:
        specs = load_specs(args.spec)
    except (OSError, UnicodeError, SpecError) as exc:
        parser.exit(2, f"Invalid experiment batch: {exc}\n")

    for spec in specs:
        print(f"{spec.id}: scenario={spec.scenario} policy={spec.policy_mode} trials={spec.trials}")
    print(f"Validated {len(specs)} experiments / {sum(spec.trials for spec in specs)} planned trials.")
    print("Dry run only: no agents or subprocesses started.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
