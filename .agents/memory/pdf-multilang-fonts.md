---
name: PDF multi-language font pitfalls
description: reportlab + arabic_reshaper / RGBA image gotchas that caused device-visible tofu and black boxes
---
- Rubik (even the full Google build) has base Arabic (U+0600–06FF) but NOT Arabic Presentation Forms (U+FE70–FEFF). arabic_reshaper outputs presentation forms, so shaped Arabic renders tofu in Rubik. Use a dedicated Arabic font that covers presentation forms (Amiri) and verify 0xFECB (shaped ع) at register time, not just 0x0639.
**Why:** two device reviews failed on silent tofu; charToGlyph checks on base codepoints passed while rendered text still broke.
**How to apply:** any reportlab text going through arabic_reshaper must probe the SHAPED codepoint; mixed Hebrew/Arabic/CJK strings need per-run <font face> wrapping (Rubik lacks both Arabic PF and CJK).
- PIL convert('RGB') on RGBA turns transparent pixels black — flatten onto white via alpha-mask paste before JPEG encode.
- Add a pre-render font-fitness gate (probe char per language → explicit 500 + log) instead of letting reportlab render tofu silently.
