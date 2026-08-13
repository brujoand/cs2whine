#!/usr/bin/env bash
#
# Shared helper for the git hooks in this directory.

set -e

# Run pre-commit, finding it wherever the toolchain put it.
#
# The tools here are mise shims rather than system packages, and a git hook does
# not inherit an interactive shell's PATH -- a GUI client or an editor's commit
# box has neither. Falling back to `mise exec` is what keeps the hook working
# outside a terminal.
run_pre_commit() {
  if command -v pre-commit >/dev/null 2>&1; then
    pre-commit "$@"
  elif command -v mise >/dev/null 2>&1; then
    mise exec -- pre-commit "$@"
  else
    # Not a hard failure: CI runs the same hooks on every pull request, so a
    # missing local toolchain must not make the repo uncommittable.
    echo "pre-commit not found -- skipping local checks. Run: mise install" >&2
    return 0
  fi
}
