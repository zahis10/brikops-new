import re

ISRAELI_MOBILE_PREFIXES = {'50', '51', '52', '53', '54', '55', '56', '57', '58', '59'}
ISRAELI_LANDLINE_PREFIXES = {'2', '3', '4', '7', '8', '9'}

def normalize_israeli_phone(raw_input: str, allow_landline: bool = False) -> dict:
    if not raw_input or not isinstance(raw_input, str):
        raise ValueError('יש להזין מספר טלפון')

    phone_raw = raw_input.strip()
    cleaned = re.sub(r'[\s\-\(\)\.\u200e\u200f\u200b\u200c\u200d\u2028\u2029\u202a-\u202e\u2066-\u2069\ufeff\u00a0]', '', phone_raw)

    if not cleaned:
        raise ValueError('יש להזין מספר טלפון')

    if not re.match(r'^[\d+]+$', cleaned):
        raise ValueError('מספר טלפון יכול להכיל ספרות בלבד')

    if cleaned.startswith('+972'):
        digits_after = cleaned[4:]
        if len(digits_after) == 9:
            prefix = digits_after[:2]
            if prefix in ISRAELI_MOBILE_PREFIXES:
                return {'phone_e164': cleaned, 'phone_raw': phone_raw}
        if allow_landline and len(digits_after) in (8, 9):
            first = digits_after[0]
            if first in ISRAELI_LANDLINE_PREFIXES:
                return {'phone_e164': cleaned, 'phone_raw': phone_raw, 'is_landline': True}
        if len(digits_after) == 9 and digits_after[:2] not in ISRAELI_MOBILE_PREFIXES:
            if not allow_landline:
                raise ValueError('יש להזין מספר נייד ישראלי תקין (05X). מספרים קוויים אינם נתמכים')
        raise ValueError('מספר טלפון ישראלי חייב להכיל 9 ספרות אחרי +972')

    if cleaned.startswith('972') and len(cleaned) == 12:
        digits_after = cleaned[3:]
        prefix = digits_after[:2]
        if prefix in ISRAELI_MOBILE_PREFIXES:
            return {'phone_e164': '+' + cleaned, 'phone_raw': phone_raw}
        if allow_landline:
            first = digits_after[0]
            if first in ISRAELI_LANDLINE_PREFIXES:
                return {'phone_e164': '+' + cleaned, 'phone_raw': phone_raw, 'is_landline': True}
        raise ValueError('יש להזין מספר נייד ישראלי תקין (05X)')

    if cleaned.startswith('972') and len(cleaned) == 11 and allow_landline:
        digits_after = cleaned[3:]
        first = digits_after[0]
        if first in ISRAELI_LANDLINE_PREFIXES:
            return {'phone_e164': '+' + cleaned, 'phone_raw': phone_raw, 'is_landline': True}

    if cleaned.startswith('0') and len(cleaned) == 10:
        prefix = cleaned[1:3]
        if prefix in ISRAELI_MOBILE_PREFIXES:
            return {'phone_e164': '+972' + cleaned[1:], 'phone_raw': phone_raw}
        if allow_landline:
            first = cleaned[1]
            if first in ISRAELI_LANDLINE_PREFIXES:
                return {'phone_e164': '+972' + cleaned[1:], 'phone_raw': phone_raw, 'is_landline': True}
        raise ValueError('יש להזין מספר נייד ישראלי תקין (05X)')

    if cleaned.startswith('0') and len(cleaned) == 9 and allow_landline:
        first = cleaned[1]
        if first in ISRAELI_LANDLINE_PREFIXES:
            return {'phone_e164': '+972' + cleaned[1:], 'phone_raw': phone_raw, 'is_landline': True}

    if cleaned.startswith('5') and len(cleaned) == 9:
        prefix = cleaned[:2]
        if prefix not in ISRAELI_MOBILE_PREFIXES:
            raise ValueError('יש להזין מספר נייד ישראלי תקין (05X)')
        return {'phone_e164': '+972' + cleaned, 'phone_raw': phone_raw}

    if cleaned.startswith('0') and len(cleaned) in (9, 10):
        first_digit = cleaned[1] if len(cleaned) > 1 else ''
        if first_digit in ISRAELI_LANDLINE_PREFIXES:
            if not allow_landline:
                raise ValueError('יש להזין מספר נייד ישראלי תקין (05X). מספרים קוויים אינם נתמכים')

    raise ValueError('מספר לא תקין. אפשר להזין 050… או +972… (נמיר אוטומטית)')


def clean_phone_for_import(raw_input) -> str:
    if raw_input is None:
        return ""
    val = str(raw_input).strip()
    if not val:
        return ""
    val = re.sub(r"['\"\s\-\.\(\)]", "", val)
    if not val:
        return ""
    if val[0] != '0' and val[0] != '+' and val[0].isdigit() and len(val) in (8, 9):
        val = '0' + val
    return val


def format_local_display(phone_e164: str) -> str:
    if not phone_e164 or not phone_e164.startswith('+972'):
        return phone_e164 or ''
    digits = phone_e164[4:]
    if len(digits) != 9:
        return phone_e164
    return f'0{digits[0:2]}-{digits[2:5]}-{digits[5:]}'
