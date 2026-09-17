---
name: Review evidence preservation
description: Preserving historical review text while appending large verification sections
---

Verify that the original review remains an exact byte prefix after appending a new evidence section. Repeated approval markers are not unique end-of-file anchors.

**Why:** A patch anchored on the recurring approval marker inserted new evidence inside an older section. A subsequent large git-blob capture through the programmatic shell callback was shortened despite a false truncation flag.

**How to apply:** Use unique tail context for an append. When processing a large original document, write the git blob to a temporary file and read it with the file callback's explicit byte budget, rather than trusting shell output as a lossless file transport. Check byte size and original-prefix preservation before delivering; retain one consolidated new section with verification steps in order.