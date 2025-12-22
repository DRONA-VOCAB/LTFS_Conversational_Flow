"""Formatting utility functions."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


def format_customer_name(name: Optional[str], gender: Optional[str] = None) -> str:
    """
    Format customer name with proper title based on gender.
    
    Args:
        name: Customer name
        gender: Optional gender ('male', 'female', 'M', 'F')
    
    Returns:
        Formatted name with appropriate title
    """
    if not name:
        return ""
    
    name = name.strip()
    
    # If name already has a title, return as is
    if name.startswith(("Mr.", "Ms.", "Mrs.", "Dr.", "Miss")):
        return name
    
    # Determine gender
    is_female = False
    
    if gender:
        # Use provided gender
        is_female = gender.lower() in ("female", "f", "woman", "girl")
    else:
        # Simple heuristic for Indian names:
        # Names ending with 'a', 'i', 'ya', 'ika', 'ita' are often female
        name_lower = name.lower()
        female_endings = ['a', 'i', 'ya', 'ika', 'ita', 'iya', 'iya', 'priya', 'shree', 'shri']
        
        # Check if name ends with common female endings
        for ending in female_endings:
            if name_lower.endswith(ending) and len(name_lower) > len(ending):
                is_female = True
                break
        
        # Common female first names (Indian context)
        common_female_names = ['priya', 'anjali', 'kavita', 'sunita', 'meera', 'neha', 
                              'kavya', 'divya', 'shreya', 'riya', 'puja', 'sneha',
                              'radha', 'sita', 'laxmi', 'saraswati', 'durga', 'parvati']
        
        # Check if first word matches common female names
        first_word = name_lower.split()[0] if name_lower.split() else ""
        if first_word in common_female_names:
            is_female = True
    
    # Add appropriate title
    if is_female:
        return f"Ms. {name}"
    else:
        return f"Mr. {name}"


def format_date(d: Optional[date]) -> str:
    """Format date for display."""
    if not d:
        return ""
    
    return d.strftime("%d %B %Y")


def format_amount(amount: Optional[Decimal]) -> str:
    """Format amount for display."""
    if not amount:
        return ""
    
    return f"₹{amount:,.2f}"


def get_greeting() -> str:
    """Get appropriate greeting based on time of day."""
    hour = datetime.now().hour
    
    if 5 <= hour < 12:
        return "Good morning"
    elif 12 <= hour < 17:
        return "Good afternoon"
    elif 17 <= hour < 21:
        return "Good evening"
    else:
        return "Good evening"  # Default for late night

