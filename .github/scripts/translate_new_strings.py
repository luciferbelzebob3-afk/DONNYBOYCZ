#!/usr/bin/env python3
"""Translate newly introduced English UI string literals without rewriting files."""
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

API_KEY = os.environ.get("OPENAI_API_KEY")
MODEL = os.environ.get("OPENAI_TRANSLATION_MODEL", "gpt-4.1-mini")
BASE_REF = os.environ.get("TRANSLATION_BASE_REF", "origin/dev")
MAX_BYTES = 60_000
ALLOWED = {".c", ".cc", ".cpp", ".h", ".hpp", ".json", ".yaml", ".yml", ".txt", ".md", ".csv", ".xml", ".html", ".js", ".ts", ".py"}

if not API_KEY:
    print("OPENAI_API_KEY is not set; skipping automatic translation.")
    sys.exit(0)

def git(*args, check=True):
    return subprocess.run(["git", *args], check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

def ask_model(path, old_text, new_text):
    prompt = f"""You are a careful English-to-Czech software localization editor.
Inspect the new version of the file {path} against its previous version.
Return ONLY a JSON object with this exact shape: {{"replacements":[{{"source":"EXACT full string literal including quotes","translation":"replacement literal including quotes"}}]}}.
Rules:
- Include only newly introduced or changed English user-facing UI/help/error text that should be Czech.
- Do not translate identifiers, variable/function names, protocol constants, command names, API fields, file paths, URLs, licenses, technical tokens, or code.
- A source must be an exact, complete quoted literal found in NEW VERSION and must not already exist in OLD VERSION.
- Keep the same quote style and valid escaping. Preserve format placeholders, printf specifiers, braces, markup, and embedded variables exactly.
- If uncertain, omit the string. Do not output explanations or markdown.
OLD VERSION:
{old_text}
NEW VERSION:
{new_text}
"""
    payload = json.dumps({
        "model": MODEL,
        "input": prompt,
        "text": {"format": {"type": "json_object"}}
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=payload,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as response:
        data = json.loads(response.read().decode())
    output = data.get("output_text")
    if not output:
        for item in data.get("output", []):
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    output = part.get("text")
                    break
    if not output:
        raise RuntimeError(f"No structured translation returned for {path}")
    return json.loads(output).get("replacements", [])

def read_at(ref, path):
    result = subprocess.run(["git", "show", f"{ref}:{path}"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if result.returncode:
        return ""
    return result.stdout.decode("utf-8", errors="replace")

def main():
    changed = git("diff", "--name-only", "--diff-filter=ACMRT", f"{BASE_REF}...HEAD").decode().splitlines()
    total = 0
    for name in changed:
        path = Path(name)
        if path.suffix.lower() not in ALLOWED or not path.is_file():
            continue
        try:
            raw = path.read_bytes()
            if len(raw) > MAX_BYTES or b"\x00" in raw:
                continue
            new_text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        old_text = read_at(BASE_REF, name)
        try:
            replacements = ask_model(name, old_text, new_text)
        except Exception as exc:
            print(f"::warning::Translation analysis failed for {name}: {exc}")
            continue
        updated = new_text
        for item in replacements:
            source = item.get("source")
            translation = item.get("translation")
            if not isinstance(source, str) or not isinstance(translation, str) or not source or source == translation:
                continue
            # Never modify a literal that already existed in the DONNYBOYCZ base.
            if source in old_text:
                continue
            # Avoid ambiguous global substitutions and changes outside exact string literals.
            if updated.count(source) != 1:
                print(f"::warning::Skipped ambiguous string in {name}: {source[:80]}")
                continue
            updated = updated.replace(source, translation, 1)
            total += 1
        if updated != new_text:
            path.write_text(updated, encoding="utf-8", newline="")
            print(f"Translated new string(s) in {name}")
    print(f"Automatic translation completed; replacements applied: {total}")

if __name__ == "__main__":
    main()
