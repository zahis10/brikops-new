TRADE_MAP = {
    'electrical': 'חשמלאי',
    'plumbing': 'אינסטלטור',
    'painting': 'צבעי',
    'carpentry_kitchen': 'נגרות/מטבח',
    'carpentry': 'נגרות/מטבח',
    'bathroom_cabinets': 'ארונות אמבטיה',
    'finishes': 'גמרים',
    'structural': 'שלד',
    'masonry': 'שלד',
    'aluminum': 'אלומיניום',
    'metalwork': 'מסגרות',
    'flooring': 'ריצוף',
    'hvac': 'מיזוג',
    'glazing': 'חלונות/זכוכית',
    'windows': 'חלונות/זכוכית',
    'doors': 'דלתות',
    'general': 'כללי',
}

CATEGORY_TO_BUCKET = {
    'electrical': 'electrical',
    'plumbing': 'plumbing',
    'painting': 'painting',
    'carpentry': 'carpentry_kitchen',
    'carpentry_kitchen': 'carpentry_kitchen',
    'bathroom_cabinets': 'bathroom_cabinets',
    'finishes': 'finishes',
    'structural': 'structural',
    'masonry': 'structural',
    'aluminum': 'aluminum',
    'metalwork': 'metalwork',
    'flooring': 'flooring',
    'hvac': 'hvac',
    'glazing': 'glazing',
    'windows': 'glazing',
    'doors': 'doors',
    'general': 'general',
}

BUCKET_LABELS = {
    'electrical': 'חשמלאי',
    'plumbing': 'אינסטלטור',
    'painting': 'צבעי',
    'carpentry_kitchen': 'נגרות/מטבח',
    'bathroom_cabinets': 'ארונות אמבטיה',
    'finishes': 'גמרים',
    'structural': 'שלד',
    'aluminum': 'אלומיניום',
    'metalwork': 'מסגרות',
    'flooring': 'ריצוף',
    'hvac': 'מיזוג',
    'glazing': 'חלונות/זכוכית',
    'doors': 'דלתות',
    'general': 'כללי',
}


def compute_task_bucket(task, contractor_map=None, company_map=None, membership_trade_map=None):
    contractor_map = contractor_map or {}
    company_map = company_map or {}
    membership_trade_map = membership_trade_map or {}

    assignee_id = task.get('assignee_id')
    if assignee_id and assignee_id in membership_trade_map:
        trade = membership_trade_map[assignee_id]
        bucket_key = CATEGORY_TO_BUCKET.get(trade, trade)
        return {
            'bucket_key': bucket_key,
            'label_he': BUCKET_LABELS.get(bucket_key, bucket_key),
            'source': 'membership',
        }

    company_id = task.get('company_id')
    if company_id and company_id in company_map:
        trade = company_map[company_id]
        bucket_key = CATEGORY_TO_BUCKET.get(trade, trade)
        return {
            'bucket_key': bucket_key,
            'label_he': BUCKET_LABELS.get(bucket_key, bucket_key),
            'source': 'company',
        }

    if assignee_id and assignee_id in contractor_map:
        trade = contractor_map[assignee_id]
        bucket_key = CATEGORY_TO_BUCKET.get(trade, trade)
        return {
            'bucket_key': bucket_key,
            'label_he': BUCKET_LABELS.get(bucket_key, bucket_key),
            'source': 'assignee',
        }

    category = task.get('category', 'general')
    bucket_key = CATEGORY_TO_BUCKET.get(category, category)
    label = BUCKET_LABELS.get(bucket_key, bucket_key)
    return {
        'bucket_key': bucket_key,
        'label_he': label,
        'source': 'category',
    }
