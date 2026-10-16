#!/usr/bin/env python3
"""Guard the destination-screen contract.

Why this exists
---------------
Six of seven destination screens declared `let onBack: () -> Void` and never used it.
`AppBar` drew no back control, and ShellView renders `destinationScreen` directly with no
wrapper, so those screens had no way out -- the user was trapped. Switching bottom-nav tabs
does not clear `destination`, so there was no exit short of killing the app.

Every signal said the code was fine. It compiled (a missing back button is valid Swift), CI
was green (CI compiles; it never renders), and the commit messages were accurate (they
described what was written, not what the user experiences). A build is not evidence that a
screen works, so this checks the one invariant that a compiler cannot: that a screen
accepting a way out actually offers it.

The rule
--------
If a file declares `onBack`, then it must either
  (a) pass it to an `AppBar`, i.e. `AppBar(onBack: onBack)`, or
  (b) draw its own back control, i.e. reference `.chevronLeft` with `onBack`.

Either is fine; silence is not. ReportsView does (b); the rest do (a).
"""
import os
import re
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "apps/ios/Sources/ChmabaPOS"


def screen_files(root):
    directory = os.path.join(root, "Screens")
    if not os.path.isdir(directory):
        sys.exit("no Screens directory under %s" % root)
    return sorted(
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if name.endswith(".swift")
    )


def main():
    problems = []
    checked = 0

    for path in screen_files(ROOT):
        text = open(path, encoding="utf-8").read()
        name = os.path.basename(path)

        # The whole rule is about files that accept an onBack.
        if not re.search(r"let onBack:\s*\(\)\s*->\s*Void", text):
            continue
        checked += 1

        forwards_to_appbar = re.search(r"AppBar\(onBack:\s*onBack\)", text) is not None
        draws_own = re.search(r"\.chevronLeft", text) is not None and \
            len(re.findall(r"\bonBack\b", text)) > 1

        if not (forwards_to_appbar or draws_own):
            # Distinguish "declared and never used at all" from "used, but the control
            # was never placed", because the fixes differ.
            uses = len(re.findall(r"\bonBack\b", text)) - 1
            detail = (
                "declared but never used"
                if uses <= 0
                else "used, but no back control is rendered"
            )
            problems.append("%s: %s" % (name, detail))

    print("screens declaring onBack: %d" % checked)
    if problems:
        print("\nNO WAY BACK FROM:")
        for problem in problems:
            print("  - %s" % problem)
        print(
            "\nEither pass it to the app bar -- AppBar(onBack: onBack) { ... } -- or draw a\n"
            "control that uses it. A screen the user cannot leave is not finished."
        )
        return 1

    print("RESULT: every screen that accepts a way out offers one")
    return 0


if __name__ == "__main__":
    sys.exit(main())
