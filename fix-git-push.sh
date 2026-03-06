#!/usr/bin/env bash
set -euo pipefail

echo "=== Fix: Remove 282MB ziQRRO7N from git history ==="
echo ""

REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
COMMIT_COUNT=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo "?")

echo "Remote: $REMOTE_URL"
echo "Unpushed commits: $COMMIT_COUNT"
echo ""

echo "Step 1: Running git-filter-repo to remove ziQRRO7N from all commits..."
git filter-repo --path ziQRRO7N --invert-paths --force

echo ""
echo "Step 2: Re-adding remote (filter-repo removes it)..."
if [ -n "$REMOTE_URL" ]; then
  git remote add origin "$REMOTE_URL" 2>/dev/null || git remote set-url origin "$REMOTE_URL"
  echo "Remote restored: $REMOTE_URL"
else
  echo "WARNING: Could not restore remote URL. You need to add it manually."
fi

echo ""
echo "Step 3: Fetching origin/main reference..."
git fetch origin main 2>/dev/null || echo "WARNING: fetch failed, but push may still work"

echo ""
echo "Step 4: Verifying no large files remain..."
LARGE_BLOBS=$(git rev-list --objects --all | git cat-file --batch-check='%(objectname) %(objecttype) %(objectsize) %(rest)' 2>/dev/null | awk '$3 > 90000000 { print $0 }')
if [ -n "$LARGE_BLOBS" ]; then
  echo "WARNING: Large objects still found:"
  echo "$LARGE_BLOBS"
else
  echo "OK: No objects >90MB found."
fi

NEW_COUNT=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo "?")
echo ""
echo "Commits after rewrite: $NEW_COUNT"
echo ""
echo "=== Done. You can now run: ./deploy.sh --prod ==="
