# Wiki source

This directory is the version-controlled source for the GitHub Wiki of **Water Leak Guard / Wasserwächter**.

The Wiki is intentionally maintained here first so documentation changes can be reviewed together with code changes.

## Publishing

Use the manual GitHub Actions workflow:

**Publish Wiki**

The workflow mirrors the complete contents of `docs/wiki/` into the repository Wiki.

GitHub creates the separate `.wiki.git` repository only after the Wiki has been initialized at least once. If the Wiki has never had a page, open the repository's **Wiki** tab and create the first page once.

If the repository-scoped `GITHUB_TOKEN` is not accepted for Git push to the Wiki repository, create a repository secret named `WIKI_TOKEN` containing a token with write access to the repository. The workflow automatically prefers `WIKI_TOKEN` when present.

## Files

- `Home.md` — Wiki start page
- `_Sidebar.md` — navigation
- `_Footer.md` — footer
- remaining Markdown files — project documentation pages

Do not rename the technical Home Assistant domain `water_leak_detection` as part of documentation naming changes.
