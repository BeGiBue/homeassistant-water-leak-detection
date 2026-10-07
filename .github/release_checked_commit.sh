#!/usr/bin/env bash
# Publication is only invoked by the manually dispatched, validation-gated jobs.
set -euo pipefail
release_version="${1:?release version required}"
[[ "${2:-}" == "--target" && "${3:-}" == "$GITHUB_SHA" ]] || exit 1

# Check the tag BEFORE checking release existence. A pre-existing tag overrides
# gh --target, so an unrelated tag must never be given a new GitHub Release.
if git ls-remote --exit-code --tags origin "refs/tags/${release_version}" >/dev/null 2>&1; then
  git fetch --no-tags origin "refs/tags/${release_version}"
  tag_commit=$(git rev-parse 'FETCH_HEAD^{commit}')
  if [[ "$tag_commit" != "$GITHUB_SHA" ]]; then
    echo "Release tag ${release_version} does not point to checked commit ${GITHUB_SHA}." >&2
    exit 1
  fi
else
  tag_status=$?
  # git ls-remote returns 2 for no matching tag, and other errors on lookup failure.
  if [[ "$tag_status" -ne 2 ]]; then
    echo "Cannot verify remote release tag." >&2
    exit "$tag_status"
  fi
fi

if gh release view "$release_version" --repo "$GITHUB_REPOSITORY" >/dev/null 2>&1; then
  # A release cannot safely be accepted if its remote tag disappeared.
  if [[ -z "${tag_commit:-}" ]]; then
    echo "Existing release has no verified tag." >&2
    exit 1
  fi
  echo "Release ${release_version} already exists at the checked commit."
  exit 0
fi

gh release create "$release_version" \
  --repo "$GITHUB_REPOSITORY" \
  --target "$GITHUB_SHA" \
  --title "Water Leak Guard ${release_version}" \
  --notes-file "RELEASE_NOTES_${release_version}.md"
