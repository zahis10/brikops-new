import re

ISRAELI_MOBILE_PREFIXES = {'50', '51', '52', '53', '54', '55', '56', '57', '58', '59'}

def normalize_israeli_phone(raw_input: str) -> dict:
    """
    Normalize Israeli phone numbers to E.164 format.
    
    Accepts: 0507569991, 507569991, +972507569991, 972507569991
    Also handles: spaces, dashes, parentheses
    
    Returns: {'phone_e164': '+972XXXXXXXXX', 'phone_raw': '<original input>'}
    Raises: ValueError with Hebrew message if invalid
    """
    if not raw_input or not isinstance(raw_input, str):
        raise ValueError('יש להזין מספר טלפון')
    
    phone_raw = raw_input.strip()
    cleaned = re.sub(r'[\s\-\(\)\.\u200e\u200f\u200b\u200c\u200d\u2028\u2029\u202a-\u202e\u2066-\u2069\ufeff\u00a0]', '', phone_raw)
    
    if not cleaned:
        raise ValueError('יש להזין מספר טלפון')
    
    if not re.match(r'^[\d+]+$', cleaned):
        raise ValueError('מספר טלפון יכול להכיל ספרות בלבד')
    
    # Case 1: Already E.164 format +972XXXXXXXXX
    if cleaned.startswith('+972'):
        digits_after = cleaned[4:]
        if len(digits_after) == 9:
            prefix = digits_after[:2]
            if prefix not in ISRAELI_MOBILE_PREFIXES:
                raise ValueError('יש להזין מספר נייד ישראלי תקין (05X). מספרים קוויים אינם נתמכים')
            return {'phone_e164': cleaned, 'phone_raw': phone_raw}
        raise ValueError('מספר טלפון ישראלי חייב להכיל 9 ספרות אחרי +972')
    
    # Case 2: 972XXXXXXXXX (without +)
    if cleaned.startswith('972') and len(cleaned) == 12:
        digits_after = cleaned[3:]
        prefix = digits_after[:2]
        if prefix not in ISRAELI_MOBILE_PREFIXES:
            raise ValueError('יש להזין מספר נייד ישראלי תקין (05X)')
        return {'phone_e164': '+' + cleaned, 'phone_raw': phone_raw}
    
    # Case 3: 0XXXXXXXXX (local with leading 0)
    if cleaned.startswith('0') and len(cleaned) == 10:
        prefix = cleaned[1:3]
        if prefix not in ISRAELI_MOBILE_PREFIXES:
            raise ValueError('יש להזין מספר נייד ישראלי תקין (05X)')
        return {'phone_e164': '+972' + cleaned[1:], 'phone_raw': phone_raw}
    
    # Case 4: 5XXXXXXXX (without leading 0)
    if cleaned.startswith('5') and len(cleaned) == 9:
        prefix = cleaned[:2]
        if prefix not in ISRAELI_MOBILE_PREFIXES:
            raise ValueError('יש להזין מספר נייד ישראלי תקין (05X)')
        return {'phone_e164': '+972' + cleaned, 'phone_raw': phone_raw}
    
    # Case 5: Israeli landline (0X-XXXXXXX where X is 2,3,4,8,9) — reject with clear message
    if cleaned.startswith('0') and len(cleaned) in (9, 10):
        first_digit = cleaned[1] if len(cleaned) > 1 else ''
        if first_digit in ('2', '3', '4', '7', '8', '9'):
            raise ValueError('יש להזין מספר נייד ישראלי תקין (05X). מספרים קוויים אינם נתמכים')
    
    raise ValueError('מספר לא תקין. אפשר להזין 050… או +972… (נמיר אוטומטית)')


def format_local_display(phone_e164: str) -> str:
    """
    Format E.164 Israeli phone to local display format.
    +972507569991 -> 050-756-9991
    """
    if not phone_e164 or not phone_e164.startswith('+972'):
        return phone_e164 or ''
    digits = phone_e164[4:]  # 507569991
    if len(digits) != 9:
        return phone_e164
    return f'0{digits[0:2]}-{digits[2:5]}-{digits[5:]}'
