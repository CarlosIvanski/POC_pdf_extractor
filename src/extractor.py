import re

def parse_euro_number(euro_str):
    """Convert European-style number like '144.570,81' to float 144570.81"""
    try:
        return float(euro_str.replace('.', '').replace(',', '.'))
    except:
        return None
    
def extract_fields(text):
    results = {
        'invoice_number': extract_field(text, r'Invoice\s*#?:?\s*(\d{3,})'),
        'date': extract_field(text, r'Date[:\s]*([\d]{2}\.[\d]{2}\.[\d]{4})'),
        'payment_details': extract_field(text, r'Payment\s+details[:\s]*([\d]{2}\.[\d]{2}\.[\d]{4})'),
    }

    total_str = extract_field(text, r'INVOICE\s+TOTAL\s+([\d\.]+,[\d]{2})\s?€?')
    results['invoice_total'] = parse_euro_number(total_str) if total_str else None

    return results

def extract_field(text, pattern):
    match = re.findall(pattern, text, re.IGNORECASE)
    return match[0].strip() if match else None
