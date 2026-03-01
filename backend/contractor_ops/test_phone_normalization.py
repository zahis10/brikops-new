"""Unit tests for Israeli phone normalization."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contractor_ops.phone_utils import normalize_israeli_phone, format_local_display

passed = 0
failed = 0

def check(label, actual, expected):
    global passed, failed
    if actual == expected:
        passed += 1
        print(f"  PASS: {label}")
    else:
        failed += 1
        print(f"  FAIL: {label}")
        print(f"    Expected: {expected}")
        print(f"    Actual:   {actual}")

def check_raises(label, fn, expected_substring=None):
    global passed, failed
    try:
        fn()
        failed += 1
        print(f"  FAIL: {label} (no exception raised)")
    except ValueError as e:
        if expected_substring and expected_substring not in str(e):
            failed += 1
            print(f"  FAIL: {label} (wrong error: {e})")
        else:
            passed += 1
            print(f"  PASS: {label}")
    except Exception as e:
        failed += 1
        print(f"  FAIL: {label} (unexpected exception: {type(e).__name__}: {e})")


print("=" * 60)
print("PHONE NORMALIZATION — UNIT TESTS")
print("=" * 60)

# === Valid Inputs ===
print("\n--- Valid Inputs ---")

# Local format with leading 0
result = normalize_israeli_phone('0507569991')
check('Local 0507569991 → e164', result['phone_e164'], '+972507569991')
check('Local 0507569991 → raw', result['phone_raw'], '0507569991')

# Without leading 0
result = normalize_israeli_phone('507569991')
check('Short 507569991 → e164', result['phone_e164'], '+972507569991')

# Full E.164
result = normalize_israeli_phone('+972507569991')
check('E164 +972507569991 → e164', result['phone_e164'], '+972507569991')

# Without + prefix
result = normalize_israeli_phone('972507569991')
check('No-plus 972507569991 → e164', result['phone_e164'], '+972507569991')

# With dashes
result = normalize_israeli_phone('050-756-9991')
check('Dashed 050-756-9991 → e164', result['phone_e164'], '+972507569991')

# With spaces
result = normalize_israeli_phone('050 756 9991')
check('Spaced 050 756 9991 → e164', result['phone_e164'], '+972507569991')

# With parentheses
result = normalize_israeli_phone('(050) 7569991')
check('Parens (050) 7569991 → e164', result['phone_e164'], '+972507569991')

# With dots
result = normalize_israeli_phone('050.756.9991')
check('Dots 050.756.9991 → e164', result['phone_e164'], '+972507569991')

# Mixed separators
result = normalize_israeli_phone('+972-50-756-9991')
check('Mixed +972-50-756-9991 → e164', result['phone_e164'], '+972507569991')

# Different mobile prefixes
for prefix in ['50', '51', '52', '53', '54', '55', '58']:
    result = normalize_israeli_phone(f'0{prefix}1234567')
    check(f'Prefix 0{prefix} → e164', result['phone_e164'], f'+972{prefix}1234567')

# phone_raw preserved
result = normalize_israeli_phone('  050-756-9991  ')
check('Raw preserves trimmed input', result['phone_raw'], '050-756-9991')

# === Invalid Inputs ===
print("\n--- Invalid Inputs ---")

check_raises('Empty string', lambda: normalize_israeli_phone(''), 'יש להזין')
check_raises('None input', lambda: normalize_israeli_phone(None), 'יש להזין')
check_raises('Only spaces', lambda: normalize_israeli_phone('   '), 'יש להזין')
check_raises('Letters', lambda: normalize_israeli_phone('abcdefgh'), 'ספרות בלבד')
check_raises('Mixed letters+digits', lambda: normalize_israeli_phone('050abc1234'), 'ספרות בלבד')
check_raises('Too short', lambda: normalize_israeli_phone('050123'), 'מספר לא תקין')
check_raises('Too long local', lambda: normalize_israeli_phone('05012345678'), 'מספר לא תקין')
check_raises('Landline 02', lambda: normalize_israeli_phone('021234567'), 'נייד ישראלי')
check_raises('Landline 03', lambda: normalize_israeli_phone('031234567'), 'נייד ישראלי')
check_raises('Landline 04', lambda: normalize_israeli_phone('041234567'), 'נייד ישראלי')
check_raises('Landline 08', lambda: normalize_israeli_phone('081234567'), 'נייד ישראלי')
check_raises('Landline 09', lambda: normalize_israeli_phone('091234567'), 'נייד ישראלי')
check_raises('Non-Israeli +1', lambda: normalize_israeli_phone('+12025551234'), 'מספר לא תקין')
check_raises('Non-Israeli +44', lambda: normalize_israeli_phone('+447911123456'), 'מספר לא תקין')
check_raises('E164 wrong digits', lambda: normalize_israeli_phone('+9722123456'), '9 ספרות')
check_raises('E164 landline +97221234567', lambda: normalize_israeli_phone('+97221234567'), '9 ספרות')
check_raises('E164 landline +972212345678', lambda: normalize_israeli_phone('+972212345678'), 'נייד ישראלי')
check_raises('E164 mobile prefix but landline', lambda: normalize_israeli_phone('+97221234567890'), '9 ספרות')

# === Display Format ===
print("\n--- Display Format ---")

check('Display +972507569991', format_local_display('+972507569991'), '050-756-9991')
check('Display +972521234567', format_local_display('+972521234567'), '052-123-4567')
check('Display empty', format_local_display(''), '')
check('Display None', format_local_display(None), '')
check('Display non-Israeli', format_local_display('+12025551234'), '+12025551234')

# === Dedup Verification ===
print("\n--- Dedup: Same number, different formats → same E.164 ---")

formats = ['0507569991', '507569991', '+972507569991', '972507569991',
           '050-756-9991', '050 756 9991', '(050)7569991']
e164_results = [normalize_israeli_phone(f)['phone_e164'] for f in formats]
all_same = all(r == '+972507569991' for r in e164_results)
check('All 7 formats → same E.164', all_same, True)

print("\n" + "=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
print("=" * 60)

if failed > 0:
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
