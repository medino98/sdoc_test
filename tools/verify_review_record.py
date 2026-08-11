#!/usr/bin/env python3
"""Gate a PR on its REVIEW_RECORD being filled in.

Complements `strictdoc export`, which proves the document parses against
grammar.sgra but is happy with a record still full of template placeholders.
This checks the parts a schema cannot: that a record for this PR exists, that
every placeholder has been replaced, and that the record names the files the
PR touches.

A placeholder is any <angle-bracketed> run of text left in the record. An
earlier version instead compared the record against the placeholder strings
found in the template, which fails open: someone filled the template in with a
real review, so the list came back empty and a record consisting of nothing but
placeholders was reported as complete. Deriving the rule from a file anyone can
edit means the gate can be switched off by editing that file, so the rule is
structural now and the template is only checked for still being a template.

The cost is that a finding statement cannot contain literal angle brackets --
write `#include <vector>` as "include vector" or the check will call it an
unfilled placeholder.

Exits non-zero on any failure, listing every problem at once.
"""

import argparse
import os
import re
import sys

RECORD_OPEN = "[[REVIEW_RECORD]]"
RECORD_CLOSE = "[[/REVIEW_RECORD]]"

# StrictDoc's multiline-field delimiters are made of angle brackets, so the
# tail of one field and the head of the next ("<<<\nFIELD: >>>") reads as a
# placeholder. Both are masked to \0 before scanning, which no placeholder may
# then span.
DELIMITER_RE = re.compile(r">>>|<<<")
PLACEHOLDER_RE = re.compile(r"<[^<>\0]+>", re.DOTALL)
DUR_RE = re.compile(
    r"^DOCUMENT_UNDER_REVIEW:[ \t]*>>>\n(?P<body>.*?)^<<<$",
    re.MULTILINE | re.DOTALL,
)
DECISION_RE = re.compile(r"^DECISION: (?P<value>.+)$", re.MULTILINE)
FINDING_RE = re.compile(
    r"^\[FINDING\]$(?P<body>.*?)(?=^\[|\Z)", re.MULTILINE | re.DOTALL
)
FIELD_RE = r"^{}: (?P<value>.+)$"

RELEASED = "To-be-released"


def read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        print(f"verify-review: {path}: {exc}", file=sys.stderr)
        sys.exit(1)


def find_record(text: str, uid: str) -> str | None:
    for match in re.finditer(re.escape(RECORD_OPEN), text):
        start = match.start()
        close = text.find(RECORD_CLOSE, start)
        if close == -1:
            return None
        block = text[start : close + len(RECORD_CLOSE)]
        if re.search(rf"^UID: {re.escape(uid)}$", block, re.MULTILINE):
            return block
    return None


def mask_delimiters(text: str) -> str:
    return DELIMITER_RE.sub("\0\0\0", text)


def placeholders_in(text: str) -> list[str]:
    """Every <...> run in `text`, longest first.

    Longest first so an overlapping match reports the most specific placeholder
    rather than a fragment of it.
    """
    found = {
        match.group(0) for match in PLACEHOLDER_RE.finditer(mask_delimiters(text))
    }
    return sorted(found, key=len, reverse=True)


def check_template(template_text: str) -> list[str]:
    """Guard the template against having been used as a review record.

    The seeder copies this file, so a template that has been filled in produces
    records that are wrong from the first line -- and its UID stem no longer
    gets rewritten, so every PR would append the same colliding UID.
    """
    problems = []
    if not placeholders_in(template_text):
        problems.append(
            "the template has no placeholders left -- it looks like it was "
            "filled in as a review record; restore it and move the content "
            "into the review document"
        )
    if not re.search(r"^UID: REVIEW-RN$", template_text, re.MULTILINE):
        problems.append(
            "the template's record UID is not 'REVIEW-RN', so the seeder "
            "cannot rewrite it into a per-PR UID"
        )
    return problems


def quote(text: str) -> str:
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= 60 else collapsed[:57] + "..."


def check(record: str, require_decision: bool,
          require_closed_findings: bool) -> list[str]:
    problems: list[str] = []

    for placeholder in placeholders_in(record):
        problems.append(f"unfilled placeholder: {quote(placeholder)}")

    dur = DUR_RE.search(record)
    if dur is None:
        problems.append("DOCUMENT_UNDER_REVIEW block is missing")
    else:
        listed = [line for line in dur.group("body").splitlines() if line.strip()]
        if not listed or listed == ["(no files changed)"]:
            problems.append("DOCUMENT_UNDER_REVIEW lists no files")

    findings = [match.group("body") for match in FINDING_RE.finditer(record)]

    if require_decision:
        decision = DECISION_RE.search(record)
        if decision is None:
            problems.append("DECISION field is missing")
        elif decision.group("value").strip() != RELEASED:
            problems.append(
                f"DECISION is '{decision.group('value').strip()}', "
                f"expected '{RELEASED}'"
            )

    if require_closed_findings:
        for body in findings:
            status = re.search(FIELD_RE.format("FINDING_STATUS"), body, re.MULTILINE)
            uid = re.search(FIELD_RE.format("UID"), body, re.MULTILINE)
            if status is not None and status.group("value").strip() == "Open":
                name = uid.group("value").strip() if uid else "(no UID)"
                problems.append(f"finding {name} is still Open")

    return problems


def summarize(uid: str, doc: str, problems: list[str], finding_count: int) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = [f"### Review record `{uid}`", ""]
    if problems:
        lines.append(f"Not ready to merge -- {len(problems)} problem(s) in `{doc}`:")
        lines.append("")
        lines += [f"- {problem}" for problem in problems]
        lines.append("")
        lines.append(
            "Fill the record in (`gh pr checkout <n> && strictdoc server .`, "
            "or edit the file directly), then push."
        )
    else:
        lines.append(f"Complete in `{doc}` -- {finding_count} finding(s) recorded.")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", type=int, required=True, help="PR number")
    parser.add_argument("--doc", default="src/LVGL_Safe_PoC_Review.sdoc")
    parser.add_argument(
        "--template", default="review_templates/Review_Record_TEMPLATE.sdoc"
    )
    parser.add_argument(
        "--require-decision",
        action="store_true",
        help=f"also require DECISION to be '{RELEASED}'",
    )
    parser.add_argument(
        "--require-closed-findings",
        action="store_true",
        help="also require every FINDING_STATUS to be Closed",
    )
    args = parser.parse_args()

    uid = f"REVIEW-PR{args.pr}"
    record = find_record(read(args.doc), uid)
    problems = check_template(read(args.template))

    if record is None:
        problems.append(f"no [[REVIEW_RECORD]] with UID {uid} in {args.doc}")
        finding_count = 0
    else:
        problems += check(
            record, args.require_decision, args.require_closed_findings
        )
        finding_count = len(FINDING_RE.findall(record))

    summarize(uid, args.doc, problems, finding_count)

    if problems:
        print(f"verify-review: {uid} is not ready:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"verify-review: {uid} complete ({finding_count} finding(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
