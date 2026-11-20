#!/usr/bin/env python3
"""Small, dependency-free Gemini API fallback for qualitative research roles."""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


MODEL = "gemini-3.8-flash"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-file", required=True)
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY is missing", file=sys.stderr)
        return 2

    with open(args.prompt_file, encoding="utf-8") as prompt_file:
        prompt = prompt_file.read()

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "thinkingConfig": {"thinkingLevel": "HIGH"},
        },
    }
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        print(f"Gemini API returned HTTP {error.code}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"Gemini API request failed: {type(error).__name__}", file=sys.stderr)
        return 1

    parts = result.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    text = "\n".join(part.get("text", "") for part in parts if part.get("text"))
    if not text.strip():
        print("Gemini API returned no text candidate", file=sys.stderr)
        return 1
    sys.stdout.write(text.rstrip() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
