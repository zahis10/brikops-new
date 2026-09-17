---
name: Spare photo upload policy
description: Intentional simplicity and content-type decisions for optional flooring photos
---

Treat per-category and per-unit photo counts as preflight-only UX caps, not concurrency guarantees. Do not add conditional persistence or compensating upload-orphan cleanup without renewed approval.

**Why:** The user explicitly rejected that added complexity. Shared request-rate, byte-rate, file-size and organization-quota safeguards are the intended protective controls.

**How to apply:** Preserve the simple upload flow when maintaining optional spare-flooring documentation. A proposal to enforce atomic count limits is a product-policy change, not a missing implementation fix.

Derive both object extension and storage MIME from recognized image bytes, after the existing declared extension/MIME gates.

**Why:** The app's compression path can relabel content; declared MIME alone can disagree with the actual image format.

**How to apply:** Keep the content-sniff check before byte/quota/storage operations, and retain upload tests for declared-versus-sniffed mismatches.