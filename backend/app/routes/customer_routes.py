"""Customer-related API routes"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List

from schemas.customer_schemas import CustomerResponse, CustomerListResponse
from database.models import CustomerData, get_db

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=CustomerListResponse)
async def get_customers(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get list of all customers"""
    try:
        # Get total count
        count_result = await db.execute(select(func.count(CustomerData.id)))
        total = count_result.scalar()
        
        # Get customers with pagination
        result = await db.execute(
            select(CustomerData).offset(skip).limit(limit)
        )
        customers = result.scalars().all()
        
        # Convert to response format
        customer_list = [CustomerResponse.model_validate(customer.to_dict()) for customer in customers]
        
        return CustomerListResponse(
            customers=customer_list,
            total=total
        )
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        
        # Log the full error for debugging
        print(f"[ERROR] Database error: {error_msg}")
        print(f"[ERROR] Traceback: {error_trace}")
        
        # Provide more helpful error messages
        if "getaddrinfo failed" in error_msg or "11001" in error_msg or "could not translate host name" in error_msg.lower() or "name or service not known" in error_msg.lower():
            from config.settings import settings
            db_url = settings.database_url or "Not set"
            # Mask password in error message
            if "@" in db_url:
                parts = db_url.split("@")
                if ":" in parts[0] and "://" in parts[0]:
                    scheme_user = parts[0].split("://")
                    if len(scheme_user) == 2:
                        user_pass = scheme_user[1].split(":")
                        if len(user_pass) >= 2:
                            db_url = f"{scheme_user[0]}://{user_pass[0]}:****@{parts[1]}"
            
            error_msg = (
                f"Database connection error: Could not resolve hostname.\n\n"
                f"This is a DNS resolution error. The hostname cannot be found.\n\n"
                f"Troubleshooting steps:\n"
                f"1. Verify the hostname in your Supabase/Neon dashboard\n"
                f"2. Try using the direct connection (non-pooler) URL\n"
                f"3. Check your network connection and DNS settings\n"
                f"4. Verify the hostname is correct: ep-green-feather-a1ks02ct-pooler.ap-southeast-1.aws.neon.tech\n\n"
                f"Current DATABASE_URL (masked): {db_url}\n"
                f"Original error: {error_msg}"
            )
        raise HTTPException(status_code=500, detail=f"Error fetching customers: {error_msg}")


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific customer by ID"""
    try:
        result = await db.execute(
            select(CustomerData).filter(CustomerData.id == customer_id)
        )
        customer = result.scalar_one_or_none()
        
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        return CustomerResponse.model_validate(customer.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        # Provide more helpful error messages
        if "getaddrinfo failed" in error_msg or "11001" in error_msg:
            error_msg = (
                f"Database connection error: Could not resolve hostname. "
                f"This usually means:\n"
                f"1. The hostname in DATABASE_URL is incorrect\n"
                f"2. Network connectivity issue\n"
                f"3. DNS resolution problem\n"
                f"Original error: {error_msg}"
            )
        raise HTTPException(status_code=500, detail=f"Error fetching customer: {error_msg}")
