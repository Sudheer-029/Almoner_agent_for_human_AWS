"""Ask your own AWS account which Bedrock model identifiers it will accept.

Bedrock rejects a bare id like `anthropic.claude-haiku-4-5`. It wants either a
versioned regional id (`anthropic.claude-...-v1:0`) or a cross-region inference
profile id (`us.anthropic.claude-...`), and which of those exist depends on the
account and the region. Rather than guess, ask:

    python scripts/list_models.py

Then export the two ids it suggests and run the pipeline.
"""

from __future__ import annotations

import os
import sys

REGION = os.environ.get("AWS_REGION", "us-west-2")


def main() -> int:
    try:
        import boto3
    except ImportError:
        print("boto3 is not installed. It ships with strands-agents; activate your venv.")
        return 1

    client = boto3.client("bedrock", region_name=REGION)
    print(f"Region: {REGION}\n")

    profiles: list[str] = []
    try:
        for p in client.list_inference_profiles().get("inferenceProfileSummaries", []):
            pid = p.get("inferenceProfileId", "")
            if "anthropic" in pid:
                profiles.append(pid)
    except Exception as exc:  # noqa: BLE001 - surface it, do not swallow
        print(f"Could not list inference profiles: {exc}\n")

    models: list[str] = []
    try:
        for m in client.list_foundation_models(byProvider="anthropic").get("modelSummaries", []):
            if "ON_DEMAND" in m.get("inferenceTypesSupported", []):
                models.append(m["modelId"])
    except Exception as exc:  # noqa: BLE001
        print(f"Could not list foundation models: {exc}\n")

    print("CROSS-REGION INFERENCE PROFILES (prefer these)")
    for pid in sorted(profiles) or ["  (none)"]:
        print("  " + pid if pid.strip() else pid)

    print("\nON-DEMAND FOUNDATION MODELS")
    for mid in sorted(models) or ["  (none)"]:
        print("  " + mid if mid.strip() else mid)

    pool = profiles or models

    def pick(*words: str) -> str | None:
        for candidate in sorted(pool, reverse=True):
            low = candidate.lower()
            if all(w in low for w in words):
                return candidate
        return None

    routine = pick("haiku") or pick("sonnet")
    judgment = pick("sonnet") or pick("opus") or routine

    print("\n" + "-" * 64)
    if routine and judgment:
        print("Add these to your shell, then re-run `python -m almoner.run`:\n")
        print(f'  export AWS_REGION="{REGION}"')
        print(f'  export ALMONER_ROUTINE_MODEL="{routine}"')
        print(f'  export ALMONER_JUDGMENT_MODEL="{judgment}"')
    else:
        print("No Anthropic models found in this region. Check the region, or that the")
        print("account has invoked an Anthropic model once (some accounts must submit")
        print("use-case details on first use).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
