"""Customer-related schema definitions"""
from pydantic import BaseModel
from typing import Optional, List


class CustomerResponse(BaseModel):
    """Response schema for customer data"""
    id: int
    customer_name: str
    contact_number: Optional[str] = None


class CustomerListResponse(BaseModel):
    """Response schema for customers list"""
    customers: List[CustomerResponse]
    total: int
