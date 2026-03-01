# M3: Phone Normalization — Proof of Delivery

**Status**: COMPLETE
**Date**: 2026-02-17
**Milestone**: M3 — Israeli Phone Normalization

---

## Feature Summary

All phone number inputs (invite creation, user registration, OTP authentication) now accept multiple Israeli mobile formats and normalize to a single canonical E.164 format (`+972XXXXXXXXX`) for storage. Users see friendly local display format (`050-756-9991`).

### Supported Input Formats

| Input Format | Example | Stored As |
|---|---|---|
| Local (10-digit) | `0507569991` | `+972507569991` |
| Short (9-digit, no leading 0) | `507569991` | `+972507569991` |
| E.164 (international) | `+972507569991` | `+972507569991` |
| With separators | `050-756-9991` | `+972507569991` |

### Validation Rules

- **Mobile-only**: Accepts 05X prefixes only (050-059)
- **Landline rejection**: 02, 03, 04, 08, 09 prefixes → 422 error
- **Digits only**: Non-numeric characters (after separator stripping) → 422
- **Length check**: Must be exactly 9 digits after +972
- **Hebrew error messages**: All validation errors in Hebrew

---

## Test Results

### Unit Tests: 42/42 PASSED
- File: `backend/contractor_ops/test_phone_normalization.py`
- Covers: all 4 input formats, validation rules, edge cases, Hebrew errors, display formatting, dedup equivalence

### E2E Phone Normalization: 27/27 PASSED
- File: `backend/contractor_ops/test_phone_normalization_e2e.py`
- Covers:
  1. Invite with local format (050...) → stored as E.164
  2. Invite with short format (50...) → stored as E.164
  3. Invite with dashed format (050-XXX-XXXX) → stripped and stored as E.164
  4. Invite with E.164 format → stored as-is (backward compatible)
  5. Duplicate blocking across all formats (local, E.164, short for same number)
  6. Invalid phone rejection: letters, landlines, too short, empty → 422
  7. Registration with different format → auto-link to pending invite
  8. Invite status transitions to "accepted" after auto-link
  9. OTP endpoints accept local and short formats
  10. All stored phone numbers verified as E.164

### Invite E2E Regression: 54/54 PASSED (0 regressions)
- File: `backend/contractor_ops/test_e2e_invite_proof.py`
- All existing invite flows unaffected by normalization changes
- RBAC matrix verified: Admin/PM/Management can create; Contractor/Viewer blocked
- Cross-project isolation confirmed

---

## Integration Points

### Backend (5 endpoints updated)

| Endpoint | File | Change |
|---|---|---|
| `POST /projects/{id}/invites` | `router.py` ~L1713 | Normalize `phone` → `target_phone` (E.164) + store `phone_raw` |
| `POST /auth/register` | `router.py` ~L202 | Normalize `phone_e164` field if provided |
| `POST /auth/request-otp` | `onboarding_router.py` ~L97 | Normalize before OTP generation |
| `POST /auth/verify-otp` | `onboarding_router.py` ~L113 | Normalize before lookup |
| `POST /auth/register-with-phone` | `onboarding_router.py` ~L176 | Normalize before user creation |

### Frontend (4 components updated)

| Component | Changes |
|---|---|
| `ManagementPanel.js` | 2 phone inputs: placeholder "05X-XXXXXXX", inputMode="tel" |
| `ProjectControlPage.js` | Invite form: placeholder "05X-XXXXXXX", inputMode="tel"; invite list: E.164→local display |
| `PhoneLoginPage.js` | Already had formatPhoneToE164; updated placeholder and Hebrew errors |
| Invite display | All E.164 numbers displayed as `050-756-9991` format |

### Migration Script

- File: `backend/scripts/normalize_phones.py`
- Idempotent: safe to re-run
- Collections: `users.phone_e164`, `invites.target_phone`
- Results: Skips already-normalized E.164 values; reports failures (test artifacts with hex characters)

---

## Files Modified/Created

### New Files
- `backend/contractor_ops/phone_utils.py` — Core normalization function
- `backend/contractor_ops/test_phone_normalization.py` — 42 unit tests
- `backend/contractor_ops/test_phone_normalization_e2e.py` — 27 E2E checks
- `backend/scripts/normalize_phones.py` — One-time migration script

### Modified Files
- `backend/contractor_ops/router.py` — Invite create + register normalization
- `backend/contractor_ops/onboarding_router.py` — OTP + phone registration normalization
- `backend/contractor_ops/test_e2e_invite_proof.py` — Numeric-only test suffixes (M3 adaptation)
- `frontend/src/components/ManagementPanel.js` — Phone input UX
- `frontend/src/pages/ProjectControlPage.js` — Phone input UX + display formatting

---

## Key Design Decisions

1. **Normalize at API boundary**: All normalization happens at the point of entry (API endpoints), not in the database layer. This ensures consistent storage regardless of input path.

2. **Dual storage**: `phone_e164` (canonical, for matching) + `phone_raw` (original input, for audit). This supports both deduplication and traceability.

3. **Mobile-only validation**: Israeli landlines (02, 03, etc.) are rejected at the API level since WhatsApp notifications only work with mobile numbers.

4. **Backward compatible**: Existing E.164 numbers pass through unchanged. The migration script is additive (adds `phone_raw` where missing) and never breaks existing data.

5. **Hebrew error messages**: All validation errors are in Hebrew to match the app's target audience.
