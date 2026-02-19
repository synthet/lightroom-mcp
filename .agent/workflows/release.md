---
description: update changelog; commit; push
---

# Release Workflow

This workflow automates the process of updating the project's changelog, committing the changes, and pushing them to the remote repository.

## Steps

1. **Summarize Changes**
   - Review recent commits and staged changes to identify what has been added, changed, or fixed.
   - Use `git log` and `git diff` as needed.

2. **Update Changelog**
   - Open [CHANGELOG.md](file:///d:/Projects/lightroom-mcp/CHANGELOG.md).
   - Add a new version entry at the top (under the header) following the "Keep a Changelog" format.
   - Use the current date and increment the version based on [Semantic Versioning](https://semver.org/).
   - Populate the "Added", "Changed", and "Fixed" sections based on your summary.

// turbo
3. **Stage and Commit**
   - Stage the updated `CHANGELOG.md` and any other relevant files.
   - Create a descriptive commit message (e.g., `docs: update changelog for version X.Y.Z`).
   - `git add CHANGELOG.md`
   - `git commit -m "docs: update changelog for version X.Y.Z"`

// turbo
4. **Push Changes**
   - Push the current branch to the remote repository.
   - `git push`
