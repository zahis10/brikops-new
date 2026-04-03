SIGNATURES = {
    'default': {
        'name': 'BrikOps',
        'title': 'ניהול ליקויי בנייה חכם',
        'email': 'info@brikops.com',
    },
    'support': {
        'name': 'צוות התמיכה',
        'title': 'BrikOps Support',
        'email': 'support@brikops.com',
    },
    'invoice': {
        'name': 'מחלקת חשבונות',
        'title': 'BrikOps Billing',
        'email': 'invoice@brikops.com',
    },
}


def wrap_email(body_html: str, signature_type: str = 'default') -> str:
    sig = SIGNATURES.get(signature_type, SIGNATURES['default'])
    return f'''<!DOCTYPE html>
<html dir="rtl" lang="he">
<head><meta charset="utf-8"></head>
<body style="margin: 0; padding: 0; background: #f4f4f4;">
<div style="max-width: 600px; margin: 0 auto; background: #ffffff; font-family: Arial, sans-serif;">
    {body_html}
    <div style="padding: 0 24px 24px 24px;">
        <hr style="border: none; border-top: 1px solid #ddd; margin: 24px 0;">
        <table dir="rtl" cellpadding="0" cellspacing="0" border="0" style="font-family: Arial, sans-serif;">
            <tr>
                <td style="padding-left: 16px; vertical-align: top;">
                    <img src="https://app.brikops.com/logo.png" alt="BrikOps" width="150" style="display: block; max-width: 150px; height: auto;">
                </td>
                <td style="vertical-align: top; padding-top: 2px;">
                    <p style="margin: 0 0 2px 0; font-size: 15px; font-weight: bold; color: #1a1a2e;">{sig['name']}</p>
                    <p style="margin: 0 0 8px 0; font-size: 13px; color: #666;">{sig['title']}</p>
                    <p style="margin: 0 0 2px 0; font-size: 13px; color: #333;">&#9742; <a href="tel:054-729-6949" style="color: #333; text-decoration: none;">054-729-6949</a></p>
                    <p style="margin: 0 0 2px 0; font-size: 13px; color: #333;">&#127760; <a href="https://app.brikops.com" style="color: #f57c00; text-decoration: none;">app.brikops.com</a></p>
                    <p style="margin: 0 0 0 0; font-size: 13px; color: #333;">&#9993; <a href="mailto:{sig['email']}" style="color: #f57c00; text-decoration: none;">{sig['email']}</a></p>
                </td>
            </tr>
        </table>
        <p style="margin: 16px 0 0 0; font-size: 11px; color: #999; text-align: center;">ניהול ליקויי בנייה, בקרת ביצוע ומסירות</p>
    </div>
</div>
</body>
</html>'''
