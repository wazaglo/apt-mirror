#!/usr/bin/env python3
"""Strip YAML comments from manifests without touching data payloads.

A naive `sed '/^\\s*#/d'` corrupts these files. Several ConfigMaps carry their
real content in block scalars — mirror.list, apt.conf, postmirror.sh,
snapshot.sh and the nginx configs — and those lines start with `#` while being
*data*, not commentary. Deleting them would remove the `#!/bin/bash` shebangs
and break the scripts outright.

So: walk the file, track when we are inside a block scalar, and only strip
comment lines outside one.

Refuses to touch a file that has a trailing comment (a value followed by
` # ...`), because splitting those safely needs real YAML parsing rather than
line handling. There are none in this repo; the guard is here so that if one
appears later it fails loudly instead of mangling the file.
"""
import re
import sys

BLOCK_SCALAR = re.compile(r':\s*[|>][-+0-9]*\s*(#.*)?$')
TRAILING_COMMENT = re.compile(r'^\s*[^#\s][^:]*:.*[^"\'\s]\s+#\s')


def strip(text: str) -> str:
    out = []
    block_indent = None  # None = not inside a block scalar

    for line in text.split("\n"):
        if block_indent is not None:
            # Inside a block scalar every line is payload, including blank
            # lines and lines that look like comments. Dedent is only signalled
            # by a NON-blank line at or left of the key's indent. A blank line
            # is content — treating it as dedent is what makes a naive stripper
            # eat the comments that follow the first empty line of a script.
            if line.strip() == "":
                out.append(line)
                continue
            indent = len(line) - len(line.lstrip())
            if indent > block_indent:
                out.append(line)
                continue
            block_indent = None
            # fall through and treat this line as ordinary YAML

        if TRAILING_COMMENT.match(line):
            raise SystemExit(
                f"refusing to strip: trailing comment needs YAML parsing: {line!r}"
            )

        if re.match(r'^\s*#', line):
            continue  # whole-line comment

        m = BLOCK_SCALAR.search(line)
        out.append(line)
        if m:
            # A block scalar's content must be indented further than this key.
            # Record the key's own indent; any line indented deeper is payload.
            block_indent = len(line) - len(line.lstrip())

    return "\n".join(out)


def main() -> int:
    changed = failed = 0
    for path in sys.argv[1:]:
        with open(path) as fh:
            original = fh.read()
        try:
            new = strip(original)
        except SystemExit as exc:
            print(f"SKIP {path}: {exc}")
            failed += 1
            continue
        if new != original:
            with open(path, "w") as fh:
                fh.write(new)
            removed = sum(
                1
                for a, b in zip(original.split("\n"), new.split("\n"))
                if a.strip().startswith("#") and a not in new.split("\n")
            )
            print(f"  {path}: stripped {removed} comment lines")
            changed += 1
        else:
            print(f"  {path}: no comments")
    print(f"\n{changed} file(s) changed, {failed} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
