#!/usr/bin/env python3
"""Seed a per-PR REVIEW_RECORD node into the cumulative review document.

Run by CI once build+test are green. The node is copied verbatim from
review_templates/Review_Record_TEMPLATE.sdoc, with exactly two fields of the
review information block filled in: REVIEW_DATE and DOCUMENT_UNDER_REVIEW.
Everything else -- title, review type, statement, participants, findings,
decision -- stays as the template's placeholders, which
tools/verify_review_record.py refuses to merge until a reviewer replaces them.

The one further edit is the UID stem: REVIEW-RN becomes REVIEW-PR<n> on the
record and its nested participant and finding nodes. That is identity rather
than content -- without it a second PR would append a duplicate UID and the
document would stop parsing, and the verifier would have no way to tell which
record belongs to this PR.

Re-running is safe: once REVIEW-PR<n> exists only DOCUMENT_UNDER_REVIEW is
refreshed, so a reviewer's work survives further pushes to the branch. That
field is owned by CI; hand-edits to it are overwritten on the next run.
"""

import argparse
import os
import re
import sys
from datetime import date

RECORD_OPEN = "[[REVIEW_RECORD]]"
RECORD_CLOSE = "[[/REVIEW_RECORD]]"

# "DOCUMENT_UNDER_REVIEW: >>>\n...\n<<<" -- the multiline-field form.
DUR_RE = re.compile(
    r"^DOCUMENT_UNDER_REVIEW:[ \t]*>>>\n.*?^<<<$",
    re.MULTILINE | re.DOTALL,
)
REVIEW_DATE_RE = re.compile(r"^REVIEW_DATE: .*$", re.MULTILINE)


def fail(message: str) -> None:
    print(f"seed-review: {message}", file=sys.stderr)
    sys.exit(1)


def read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        fail(f"{path}: {exc}")


def template_record(template_text: str) -> str:
    """Extract the single [[REVIEW_RECORD]] block from the template."""
    start = template_text.find(RECORD_OPEN)
    end = template_text.rfind(RECORD_CLOSE)
    if start == -1 or end == -1:
        fail("template has no [[REVIEW_RECORD]] block")
    return template_text[start : end + len(RECORD_CLOSE)]


def find_record(text: str, uid: str) -> tuple[int, int] | None:
    """Span of the [[REVIEW_RECORD]] block whose UID line is exactly `uid`.

    REVIEW_RECORD blocks are never nested (only [[SECTION]] nests inside one),
    so pairing each open marker with the next close marker is sufficient.
    """
    for match in re.finditer(re.escape(RECORD_OPEN), text):
        start = match.start()
        close = text.find(RECORD_CLOSE, start)
        if close == -1:
            fail("unterminated [[REVIEW_RECORD]] block in target document")
        end = close + len(RECORD_CLOSE)
        if re.search(rf"^UID: {re.escape(uid)}$", text[start:end], re.MULTILINE):
            return (start, end)
    return None


def render_dur(files: list[str]) -> str:
    body = "\n".join(files) if files else "(no files changed)"
    return f"DOCUMENT_UNDER_REVIEW: >>>\n{body}\n<<<"


def set_dur(block: str, files: list[str]) -> str:
    new_block, count = DUR_RE.subn(
        lambda _: render_dur(files), block, count=1
    )
    if count == 0:
        fail("no DOCUMENT_UNDER_REVIEW block found to update")
    return new_block


def build_record(template_text: str, uid: str, today: str,
                 files: list[str]) -> str:
    block = template_record(template_text)

    # Identity, not content: also renames the nested PARTICIPANT and FINDING
    # UIDs so two PRs never collide.
    block = re.sub(r"REVIEW-RN\b", uid, block)

    # The only two content fields CI fills. The TITLE and FINDING_DATE date
    # placeholders are deliberately left alone -- the reviewer sets those when
    # the review actually happens, which need not be today.
    block, count = REVIEW_DATE_RE.subn(f"REVIEW_DATE: {today}", block, count=1)
    if count == 0:
        fail("template has no REVIEW_DATE field")
    return set_dur(block, files)


def emit_output(**values: bool) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={'true' if value else 'false'}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", type=int, required=True, help="PR number")
    parser.add_argument("--doc", default="src/LVGL_Safe_PoC_Review.sdoc")
    parser.add_argument(
        "--template", default="review_templates/Review_Record_TEMPLATE.sdoc"
    )
    parser.add_argument(
        "--files-from",
        required=True,
        help="file listing the PR's changed paths, one per line",
    )
    parser.add_argument("--today", default=date.today().isoformat())
    args = parser.parse_args()

    uid = f"REVIEW-PR{args.pr}"

    files = sorted(
        {
            line.strip()
            for line in read(args.files_from).splitlines()
            if line.strip()
            # The review record is not under review by itself, and CI's own
            # seed commit would otherwise add it to every list.
            and os.path.normpath(line.strip()) != os.path.normpath(args.doc)
        }
    )

    text = read(args.doc)
    original = text
    span = find_record(text, uid)

    if span is None:
        record = build_record(read(args.template), uid, args.today, files)
        text = text.rstrip("\n") + "\n\n" + record + "\n"
        seeded = True
    else:
        # Only the file list is refreshed on re-runs. REVIEW_DATE is left at
        # the value seeded on the first green build, so a reviewer who dated
        # the record by hand is not overruled by a later push.
        start, end = span
        text = text[:start] + set_dur(text[start:end], files) + text[end:]
        seeded = False

    changed = text != original
    if changed:
        try:
            with open(args.doc, "w", encoding="utf-8") as handle:
                handle.write(text)
        except OSError as exc:
            fail(f"{args.doc}: {exc}")

    action = "seeded" if seeded else ("updated" if changed else "already current")
    print(f"seed-review: {uid} {action} in {args.doc} ({len(files)} file(s))")
    emit_output(seeded=seeded, changed=changed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
