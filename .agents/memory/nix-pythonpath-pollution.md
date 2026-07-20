---
name: Nix PYTHONPATH pollution breaks numpy
description: replit.nix pkgs.yakut injects broken py3.12 numpy ahead of workspace py3.11 packages
---
Rule: any backend module that imports numpy (or other C-extension packages) at startup will crash boot unless workspace `.pythonlibs` resolves first on PYTHONPATH.
**Why:** `replit.nix` includes `pkgs.yakut`, which prepends a python3.12 numpy 2.2.5 Nix path to PYTHONPATH; the workspace runs python3.11, so importing that numpy fails with "No module named numpy._core._multiarray_umath".
**How to apply:** `backend/start.sh` exports PYTHONPATH with `.pythonlibs/lib/python3.11/site-packages` first before exec uvicorn (added 2026-07-20). For ad-hoc shell probes that import numpy/onnxruntime, prepend the same path manually. Root cause would be removing `pkgs.yakut` from replit.nix, but its purpose is unknown — not removed.
