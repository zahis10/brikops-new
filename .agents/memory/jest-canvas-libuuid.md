---
name: Jest canvas libuuid shim
description: How to run frontend Jest when the bundled canvas binary cannot resolve libuuid in the Replit Nix runtime.
---

When Jest fails before collection because `canvas.node` cannot resolve
`libuuid.so.1`, expose only that library through a temporary directory rather
than adding the entire system library directory to `LD_LIBRARY_PATH`.

**Why:** Adding `/usr/lib/x86_64-linux-gnu` directly can make Nix Node load the
system `libcrypto.so.3`, which lacks the OpenSSL symbol versions required by the
Node executable. A directory containing only a symlink to `libuuid.so.1` lets
the native canvas binary resolve its missing dependency while Node keeps using
its compatible Nix libraries.

**How to apply:** Create a temporary directory under `/tmp`, symlink the system
`libuuid.so.1` into it, and set `LD_LIBRARY_PATH` to that directory only for the
Jest command. Do not change project manifests or environment files for this
harness issue.