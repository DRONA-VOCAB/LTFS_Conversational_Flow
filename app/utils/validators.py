"""Response validation and compliance checking functions."""
import re
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta, date
from decimal import Decimal
from app.config import settings


# Response mapping dictionaries to minimize LLM usage
YES_RESPONSES = {
    "yes", "yep", "yeah", "yup", "correct", "right", "okay", "ok", "sure", 
    "absolutely", "indeed", "affirmative", "hmm", "hmm hmm", "haan", "ha", 
    "theek hai", "bilkul", "sahi hai"
}

NO_RESPONSES = {
    "no", "nope", "nah", "not", "incorrect", "wrong", "never", "na", 
    "nahi", "nhi", "galat", "theek nahi"
}

PAYMENT_MODE_MAPPING = {
    "online": ["online", "internet", "net banking", "netbanking", "internet banking"],
    "upi": ["upi", "phonepe", "paytm", "google pay", "gpay", "bhim"],
    "neft": ["neft", "national electronic funds transfer"],
    "rtgs": ["rtgs", "real time gross settlement"],
    "cash": ["cash", "nagad", "nagd", "physical", "hand"],
    "branch": ["branch", "bank branch", "bank", "office"],
    "outlet": ["outlet", "counter", "shop"],
    "nach": ["nach", "auto debit", "automatic", "auto", "auto debit from account"],
    "field_executive": ["field executive", "field officer", "agent", "executive", "field"]
}

PAYMENT_REASON_MAPPING = {
    "emi": ["emi", "installment", "monthly payment", "monthly"],
    "emi+charges": ["emi+charges", "emi plus charges", "emi and charges", "emi with charges"],
    "settlement": ["settlement", "settle", "full settlement"],
    "foreclosure": ["foreclosure", "foreclose", "close loan"],
    "charges": ["charges", "penalty", "late fee", "fees"],
    "loan_cancellation": ["loan cancellation", "cancel loan", "cancellation"],
    "advance_emi": ["advance emi", "advance", "prepayment", "pre pay"]
}

PAYMENT_MADE_BY_MAPPING = {
    "self": ["self", "myself", "i", "me", "main", "humne", "maine"],
    "family": ["family", "family member", "wife", "husband", "son", "daughter", 
               "father", "mother", "brother", "sister", "relative", "ghar wale"],
    "friend": ["friend", "dost", "colleague"],
    "third_party": ["third party", "agent", "someone else", "other", "dusra", "kisi aur"]
}


def validate_yes_no_response(text: str) -> Optional[bool]:
    """
    Validate yes/no response using keyword mapping.
    Returns True for yes, False for no, None if unclear.
    """
    text_lower = text.lower().strip()
    
    # Check for phrases that indicate confirmation/identity
    confirmation_phrases = [
        "it's me", "its me", "this is me", "i am", "i'm", "yeah it's me",
        "yes it's me", "yes its me", "yes this is me", "yes i am", "yes i'm",
        "correct", "right", "that's me", "thats me", "yes that's me"
    ]
    for phrase in confirmation_phrases:
        if phrase in text_lower:
            return True
    
    # Check for yes responses
    for yes_word in YES_RESPONSES:
        if yes_word in text_lower:
            return True
    
    # Check for no responses
    for no_word in NO_RESPONSES:
        if no_word in text_lower:
            return False
    
    return None


def validate_payment_mode(text: str) -> Optional[str]:
    """
    Validate payment mode from text using keyword mapping.
    Returns standardized payment mode or None.
    """
    text_lower = text.lower().strip()
    
    for mode, keywords in PAYMENT_MODE_MAPPING.items():
        for keyword in keywords:
            if keyword in text_lower:
                return mode
    
    return None


def validate_payment_reason(text: str) -> Optional[str]:
    """
    Validate payment reason from text using keyword mapping.
    Returns standardized payment reason or None.
    """
    text_lower = text.lower().strip()
    
    for reason, keywords in PAYMENT_REASON_MAPPING.items():
        for keyword in keywords:
            if keyword in text_lower:
                return reason
    
    return None


def validate_payment_made_by(text: str) -> Optional[str]:
    """
    Validate who made the payment from text using keyword mapping.
    Returns standardized value or None.
    """
    text_lower = text.lower().strip()
    
    for payer, keywords in PAYMENT_MADE_BY_MAPPING.items():
        for keyword in keywords:
            if keyword in text_lower:
                return payer
    
    return None


def extract_date_from_text(text: str) -> Optional[date]:
    """
    Extract date from text using regex patterns.
    Handles formats like: "30th", "30", "December 2nd", "November 27", "yesterday", "today", etc.
    """
    text_lower = text.lower().strip()
    today = date.today()
    
    # Handle relative dates
    if "today" in text_lower or "aaj" in text_lower:
        return today
    if "yesterday" in text_lower or "kal" in text_lower:
        return today - timedelta(days=1)
    if "day before yesterday" in text_lower or "parso" in text_lower:
        return today - timedelta(days=2)
    
    # Month name mapping
    month_names = {
        "january": 1, "jan": 1,
        "february": 2, "feb": 2,
        "march": 3, "mar": 3,
        "april": 4, "apr": 4,
        "may": 5,
        "june": 6, "jun": 6,
        "july": 7, "jul": 7,
        "august": 8, "aug": 8,
        "september": 9, "sep": 9, "sept": 9,
        "october": 10, "oct": 10,
        "november": 11, "nov": 11,
        "december": 12, "dec": 12
    }
    
    # Try to extract date with month name (e.g., "December 2nd", "November 27")
    month_day_pattern = r'\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{1,2})(?:st|nd|rd|th)?\b'
    month_day_match = re.search(month_day_pattern, text_lower)
    if month_day_match:
        month_name = month_day_match.group(1)
        day_str = month_day_match.group(2)
        if month_name in month_names:
            try:
                month_num = month_names[month_name]
                day = int(day_str)
                if 1 <= day <= 31:
                    # Try current year first
                    try:
                        return date(today.year, month_num, day)
                    except ValueError:
                        # If day doesn't exist, try previous year
                        try:
                            return date(today.year - 1, month_num, day)
                        except ValueError:
                            pass
            except (ValueError, IndexError):
                pass
    
    # Extract numeric date (1-31) - assume current or previous month
    date_pattern = r'\b(\d{1,2})(?:st|nd|rd|th)?\b'
    matches = re.findall(date_pattern, text_lower)
    
    if matches:
        try:
            day = int(matches[0])
            if 1 <= day <= 31:
                # Assume current month and year
                try:
                    return date(today.year, today.month, day)
                except ValueError:
                    # If day doesn't exist in current month, try previous month
                    if today.month == 1:
                        return date(today.year - 1, 12, day)
                    else:
                        return date(today.year, today.month - 1, day)
        except ValueError:
            pass
    
    # Try to extract full date patterns (DD/MM/YYYY, DD-MM-YYYY, etc.)
    full_date_patterns = [
        r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b',
        r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b',
    ]
    
    for pattern in full_date_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                if len(match.groups()) == 3:
                    parts = match.groups()
                    # Try DD/MM/YYYY first
                    try:
                        return date(int(parts[2]), int(parts[1]), int(parts[0]))
                    except ValueError:
                        # Try YYYY/MM/DD
                        try:
                            return date(int(parts[0]), int(parts[1]), int(parts[2]))
                        except ValueError:
                            pass
            except (ValueError, IndexError):
                pass
    
    return None


def extract_amount_from_text(text: str) -> Optional[Decimal]:
    """
    Extract amount from text using regex patterns.
    Handles formats like: "5000", "5000 rupees", "5 thousand", etc.
    """
    text_lower = text.lower().strip()
    
    # Remove common words
    text_lower = re.sub(r'\b(rupees?|rs|rs\.|inr|amount|paid)\b', '', text_lower)
    text_lower = text_lower.strip()
    
    # Extract numeric amount
    # Pattern for numbers with commas or without
    amount_pattern = r'(\d{1,3}(?:[,\s]\d{2,3})*(?:\.\d{2})?)'
    matches = re.findall(amount_pattern, text_lower)
    
    if matches:
        try:
            # Remove commas and spaces, convert to float then Decimal
            amount_str = matches[0].replace(',', '').replace(' ', '')
            return Decimal(str(float(amount_str)))
        except (ValueError, IndexError):
            pass
    
    # Handle word-based amounts (thousand, lakh, crore)
    thousand_match = re.search(r'(\d+)\s*(?:thousand|k)', text_lower)
    if thousand_match:
        try:
            return Decimal(int(thousand_match.group(1)) * 1000)
        except ValueError:
            pass
    
    lakh_match = re.search(r'(\d+)\s*(?:lakh|lac)', text_lower)
    if lakh_match:
        try:
            return Decimal(int(lakh_match.group(1)) * 100000)
        except ValueError:
            pass
    
    return None


def check_payment_compliance(
    customer_response: bool,
    file_has_payment: bool
) -> Tuple[bool, str]:
    """
    Check if payment response is compliant.
    Returns (is_compliant, note).
    """
    if not customer_response and file_has_payment:
        return False, "Customer denied payment but file shows payment - Non-Compliance"
    return True, "Payment response is compliant"


def check_date_compliance(
    customer_date: Optional[date],
    deposition_date: Optional[date]
) -> Tuple[bool, str]:
    """
    Check if payment date is compliant (within 48 hours tolerance).
    Returns (is_compliant, note).
    """
    if customer_date is None or deposition_date is None:
        return True, "Date information not available for compliance check"
    
    # Calculate difference
    date_diff = abs((customer_date - deposition_date).days)
    
    # If customer date is before or same as deposition date, it's compliant
    if customer_date <= deposition_date:
        return True, "Payment date is compliant"
    
    # If customer date is after deposition date, check if within 48 hours
    if date_diff == 0:
        return True, "Payment date matches"
    
    # If difference is 1 day and deposition is end of month, might be next day payment
    if date_diff == 1:
        # Check if deposition date is end of month (28-31)
        if deposition_date.day >= 28:
            return True, "Payment date within acceptable range (end of month scenario)"
    
    # If more than 1 day difference and customer date is after, it's non-compliant
    if customer_date > deposition_date and date_diff > 1:
        return False, f"Payment date mismatch: Customer said {customer_date}, file shows {deposition_date}"
    
    return True, "Payment date is compliant"


def check_amount_compliance(
    customer_amount: Optional[Decimal],
    file_amount: Optional[Decimal]
) -> Tuple[bool, str]:
    """
    Check if payment amount is compliant (within 500 Rs tolerance).
    Returns (is_compliant, note).
    """
    if customer_amount is None or file_amount is None:
        return True, "Amount information not available for compliance check"
    
    difference = abs(float(customer_amount - file_amount))
    
    if difference <= settings.payment_amount_tolerance:
        return True, f"Amount difference ({difference} Rs) is within tolerance"
    else:
        return False, f"Amount mismatch: Customer said {customer_amount}, file shows {file_amount}, difference {difference} Rs"


def check_payment_mode_compliance(payment_mode: str) -> Tuple[bool, str]:
    """
    Check if payment mode is compliant.
    Non-compliant modes: cash, field_executive
    Returns (is_compliant, note).
    """
    non_compliant_modes = ["cash", "field_executive"]
    
    if payment_mode in non_compliant_modes:
        return False, f"Payment mode '{payment_mode}' is non-compliant"
    
    return True, f"Payment mode '{payment_mode}' is compliant"

