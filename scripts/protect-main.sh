#!/usr/bin/env bash
# Protects the main branch: changes land only through PRs, and the "unit-tests" check must pass.
# Run once after the GitHub repo exists and the workflow has run at least once.
# Usage: scripts/protect-main.sh [owner/repo]   (defaults to the current repo)
set -euo pipefail

repo="${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"

gh api --method PUT "repos/$repo/branches/main/protection" --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["unit-tests"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON

echo "main is protected on $repo"
