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
    Handles formats like: "30th", "30", "December 2nd", "2nd December", "November 27", 
    "yesterday", "today", "02/12/2024", "2-12-2024", etc.
    """
    if not text or not text.strip():
        return None
    
    # Clean the text - remove extra whitespace and normalize
    text = text.strip()
    text_lower = text.lower().strip()
    today = date.today()
    
    # Debug logging (can be removed in production)
    import sys
    if hasattr(sys, '_getframe'):
        print(f"[DateExtractor] Input text: '{text}' -> lowercased: '{text_lower}'")
    
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
    
    # Try to extract date with month name - format: "December 2nd" or "2nd December"
    # Pattern 1: Month Day (e.g., "December 2nd", "November 27", "december 2nd")
    # More flexible pattern that handles various spacing and punctuation
    month_day_pattern1 = r'\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{1,2})(?:st|nd|rd|th)?\b'
    month_day_match1 = re.search(month_day_pattern1, text_lower)
    if month_day_match1:
        month_name = month_day_match1.group(1)
        day_str = month_day_match1.group(2)
        print(f"[DateExtractor] Pattern 1 matched: month='{month_name}', day='{day_str}'")
        if month_name in month_names:
            try:
                month_num = month_names[month_name]
                day = int(day_str)
                if 1 <= day <= 31:
                    # Try current year first
                    try:
                        extracted_date = date(today.year, month_num, day)
                        # If date is in future, use previous year
                        if extracted_date > today:
                            result = date(today.year - 1, month_num, day)
                            print(f"[DateExtractor] Extracted date (previous year): {result}")
                            return result
                        print(f"[DateExtractor] Extracted date: {extracted_date}")
                        return extracted_date
                    except ValueError:
                        # If day doesn't exist, try previous year
                        try:
                            result = date(today.year - 1, month_num, day)
                            print(f"[DateExtractor] Extracted date (previous year, ValueError case): {result}")
                            return result
                        except ValueError:
                            print(f"[DateExtractor] Invalid date: {month_num}/{day}")
                            pass
            except (ValueError, IndexError) as e:
                print(f"[DateExtractor] Error processing date: {e}")
                pass
    
    # Pattern 2: Day Month (e.g., "2nd December", "27 November")
    day_month_pattern = r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b'
    day_month_match = re.search(day_month_pattern, text_lower)
    if day_month_match:
        day_str = day_month_match.group(1)
        month_name = day_month_match.group(2)
        print(f"[DateExtractor] Pattern 2 matched: day='{day_str}', month='{month_name}'")
        if month_name in month_names:
            try:
                month_num = month_names[month_name]
                day = int(day_str)
                if 1 <= day <= 31:
                    try:
                        extracted_date = date(today.year, month_num, day)
                        # If date is in future, use previous year
                        if extracted_date > today:
                            result = date(today.year - 1, month_num, day)
                            print(f"[DateExtractor] Extracted date (Pattern 2, previous year): {result}")
                            return result
                        print(f"[DateExtractor] Extracted date (Pattern 2): {extracted_date}")
                        return extracted_date
                    except ValueError:
                        try:
                            result = date(today.year - 1, month_num, day)
                            print(f"[DateExtractor] Extracted date (Pattern 2, ValueError case): {result}")
                            return result
                        except ValueError:
                            pass
            except (ValueError, IndexError):
                pass
    
    # Try to extract full date patterns (DD/MM/YYYY, DD-MM-YYYY, etc.)
    # Indian format: DD/MM/YYYY or DD-MM-YYYY
    indian_date_pattern = r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b'
    indian_match = re.search(indian_date_pattern, text)
    if indian_match:
        try:
            day, month, year = int(indian_match.group(1)), int(indian_match.group(2)), int(indian_match.group(3))
            if 1 <= day <= 31 and 1 <= month <= 12 and 2000 <= year <= 2100:
                try:
                    return date(year, month, day)
                except ValueError:
                    pass
        except (ValueError, IndexError):
            pass
    
    # International format: YYYY/MM/DD or YYYY-MM-DD
    iso_date_pattern = r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b'
    iso_match = re.search(iso_date_pattern, text)
    if iso_match:
        try:
            year, month, day = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
            if 1 <= day <= 31 and 1 <= month <= 12 and 2000 <= year <= 2100:
                try:
                    return date(year, month, day)
                except ValueError:
                    pass
        except (ValueError, IndexError):
            pass
    
    # Extract numeric date (1-31) - but avoid matching phone numbers or amounts
    # Look for date-like patterns that are not part of phone numbers or large amounts
    # Pattern: standalone number 1-31, possibly with ordinal suffix, not followed by digits that would make it a phone/amount
    date_pattern = r'(?<!\d)\b([1-9]|[12][0-9]|3[01])(?:st|nd|rd|th)?\b(?!\s*\d{4,})'
    matches = re.findall(date_pattern, text_lower)
    
    if matches:
        try:
            day = int(matches[0])
            print(f"[DateExtractor] Pattern 3 (numeric) matched: day={day}")
            if 1 <= day <= 31:
                # Assume current month and year
                try:
                    extracted_date = date(today.year, today.month, day)
                    # If date is in future, assume previous month
                    if extracted_date > today:
                        if today.month == 1:
                            result = date(today.year - 1, 12, day)
                        else:
                            result = date(today.year, today.month - 1, day)
                        print(f"[DateExtractor] Extracted date (Pattern 3, previous month): {result}")
                        return result
                    print(f"[DateExtractor] Extracted date (Pattern 3): {extracted_date}")
                    return extracted_date
                except ValueError:
                    # If day doesn't exist in current month, try previous month
                    if today.month == 1:
                        result = date(today.year - 1, 12, day)
                    else:
                        result = date(today.year, today.month - 1, day)
                    print(f"[DateExtractor] Extracted date (Pattern 3, ValueError case): {result}")
                    return result
        except ValueError:
            pass
    
    print(f"[DateExtractor] No date extracted from text: '{text}'")
    return None


def extract_amount_from_text(text: str) -> Optional[Decimal]:
    """
    Extract amount from text using regex patterns.
    Handles formats like: "5000", "5000 rupees", "5 thousand", "5 thousand 500", 
    "2 lakh", "2.5 lakh", "50,000", etc.
    """
    text_lower = text.lower().strip()
    original_text = text_lower
    
    # Handle word-based amounts first (thousand, lakh, crore) - these are more specific
    # Pattern: "5 thousand 500" or "5 thousand"
    thousand_with_hundreds = re.search(r'(\d+(?:\.\d+)?)\s*(?:thousand|k)\s*(?:and\s*)?(\d+)?', text_lower)
    if thousand_with_hundreds:
        try:
            thousands = float(thousand_with_hundreds.group(1))
            hundreds = float(thousand_with_hundreds.group(2)) if thousand_with_hundreds.group(2) else 0
            return Decimal(int(thousands * 1000 + hundreds))
        except (ValueError, AttributeError):
            pass
    
    # Pattern: "2.5 lakh" or "2 lakh"
    lakh_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:lakh|lac)', text_lower)
    if lakh_match:
        try:
            lakhs = float(lakh_match.group(1))
            return Decimal(int(lakhs * 100000))
        except ValueError:
            pass
    
    # Pattern: "2 crore" or "2.5 crore"
    crore_match = re.search(r'(\d+(?:\.\d+)?)\s*crore', text_lower)
    if crore_match:
        try:
            crores = float(crore_match.group(1))
            return Decimal(int(crores * 10000000))
        except ValueError:
            pass
    
    # Pattern: "5 thousand" (simple)
    simple_thousand_match = re.search(r'(\d+)\s*(?:thousand|k)\b', text_lower)
    if simple_thousand_match:
        try:
            return Decimal(int(simple_thousand_match.group(1)) * 1000)
        except ValueError:
            pass
    
    # Remove common words that might interfere
    text_lower = re.sub(r'\b(rupees?|rs|rs\.|inr|amount|paid|only|total)\b', '', text_lower)
    text_lower = text_lower.strip()
    
    # Extract numeric amount - improved pattern to avoid phone numbers
    # Pattern for numbers with commas: "50,000", "5,00,000", etc.
    # Also handles numbers without commas: "5000", "50000"
    # Avoid matching phone numbers (typically 10 digits) or very small numbers that might be dates
    
    # First, try to find amounts with commas (more likely to be amounts)
    comma_amount_pattern = r'(\d{1,2}(?:,\d{2,3})+)(?:\.\d{2})?'
    comma_matches = re.findall(comma_amount_pattern, text_lower)
    if comma_matches:
        try:
            # Take the largest number (most likely the amount)
            amounts = []
            for match in comma_matches:
                amount_str = match.replace(',', '')
                try:
                    amount_val = float(amount_str)
                    # Filter out very small numbers (likely dates) and very large (likely phone/account numbers)
                    if 100 <= amount_val <= 999999999:  # Between 100 and 999 crores
                        amounts.append(amount_val)
                except ValueError:
                    pass
            
            if amounts:
                # Return the largest amount found
                return Decimal(str(max(amounts)))
        except (ValueError, IndexError):
            pass
    
    # Pattern for numbers without commas but with context words
    # Look for numbers that are near amount-related words
    amount_context_pattern = r'(?:rupees?|rs|rs\.|inr|amount|paid|of|is|was)\s*[:\s]*(\d{3,9})(?:\.\d{2})?'
    context_match = re.search(amount_context_pattern, original_text)
    if context_match:
        try:
            amount_val = float(context_match.group(1))
            if 100 <= amount_val <= 999999999:
                return Decimal(str(amount_val))
        except ValueError:
            pass
    
    # Pattern for standalone large numbers (4-9 digits, likely amounts not phone numbers)
    # Phone numbers are typically 10 digits, so we look for 4-9 digit numbers
    standalone_amount_pattern = r'(?<!\d)\b(\d{4,9})(?:\.\d{2})?\b(?!\d{4,})'
    standalone_matches = re.findall(standalone_amount_pattern, text_lower)
    if standalone_matches:
        try:
            amounts = []
            for match in standalone_matches:
                try:
                    amount_val = float(match)
                    # Filter: amounts should be reasonable (100 to 999 crores)
                    if 100 <= amount_val <= 999999999:
                        amounts.append(amount_val)
                except ValueError:
                    pass
            
            if amounts:
                # Return the largest amount found
                return Decimal(str(max(amounts)))
        except (ValueError, IndexError):
            pass
    
    # Pattern for smaller numbers (3 digits) but only if they appear with amount context
    small_amount_pattern = r'(?:rupees?|rs|rs\.|inr|amount|paid)\s*[:\s]*(\d{3})(?:\.\d{2})?'
    small_match = re.search(small_amount_pattern, original_text)
    if small_match:
        try:
            amount_val = float(small_match.group(1))
            if amount_val >= 100:
                return Decimal(str(amount_val))
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

