#!/usr/bin/env python3
"""Revoke a registered model release and preserve the operator/evidence trail."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default=os.environ.get("SMART_CATTLE_API", "http://localhost:8080"))
    parser.add_argument("--api-key", default=os.environ.get("ADMIN_API_KEY", ""))
    parser.add_argument("--release-id", type=int, required=True)
    parser.add_argument("--revoked-by", required=True)
    parser.add_argument("--evidence-reference", required=True)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()
    if not args.api_key:
        raise SystemExit("an administrator API key is required")
    payload = {"revokedBy": args.revoked_by, "evidenceReference": args.evidence_reference,
               "notes": args.notes or None}
    request = urllib.request.Request(
        f"{args.api.rstrip('/')}/api/model-releases/{args.release_id}/revoke",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {args.api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            print(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise SystemExit(f"backend rejected revocation: HTTP {error.code} {error.read().decode('utf-8', 'replace')}") from error
    except urllib.error.URLError as error:
        raise SystemExit(f"cannot reach backend: {error}") from error


if __name__ == "__main__":
    main()
