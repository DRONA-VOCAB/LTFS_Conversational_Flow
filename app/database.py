"""Database connection and session management for Neon PostgreSQL."""
import ssl
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Integer, Numeric, Date, Boolean, Text
from app.config import settings


# Process database URL for asyncpg compatibility
database_url = settings.database_url
if not database_url:
    raise ValueError("DATABASE_URL is not configured. Please set it in your .env file.")

# Convert postgresql:// to postgresql+asyncpg:// if needed
if database_url.startswith("postgresql://") and "postgresql+asyncpg://" not in database_url:
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Parse URL to handle SSL parameters for asyncpg
parsed = urlparse(database_url)
query_params = parse_qs(parsed.query)

# Extract SSL-related parameters
ssl_mode = None
connect_args = {}

# Handle sslmode parameter (convert to asyncpg's ssl format)
if 'sslmode' in query_params:
    ssl_mode_value = query_params['sslmode'][0].lower()
    # Remove sslmode from query params as asyncpg doesn't use it
    del query_params['sslmode']
    
    # Convert sslmode to asyncpg's ssl parameter
    # asyncpg uses ssl=True/False or an SSL context
    if ssl_mode_value == 'disable':
        connect_args['ssl'] = False
    else:
        # For require, prefer, allow - create SSL context for Neon
        # Create SSL context that works with Neon
        # Note: For production, you should use proper certificate verification
        # For development, we'll use a context that doesn't verify certificates
        # to avoid certificate store issues on some systems
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        connect_args['ssl'] = ssl_context
        print("[INFO] Using SSL connection without certificate verification (development mode)")

# Remove channel_binding as asyncpg doesn't support it directly
if 'channel_binding' in query_params:
    del query_params['channel_binding']

# Reconstruct URL without SSL query parameters
if query_params:
    # Rebuild query string
    new_query = urlencode(query_params, doseq=True)
    parsed = parsed._replace(query=new_query)
else:
    parsed = parsed._replace(query='')

database_url = urlunparse(parsed)

# Debug: Print the connection URL (without password for security)
if database_url:
    # Mask password in debug output
    debug_url = database_url
    if "@" in debug_url:
        parts = debug_url.split("@")
        if ":" in parts[0] and "://" in parts[0]:
            scheme_user = parts[0].split("://")
            if len(scheme_user) == 2:
                user_pass = scheme_user[1].split(":")
                if len(user_pass) >= 2:
                    debug_url = f"{scheme_user[0]}://{user_pass[0]}:****@{parts[1]}"
    print(f"[DEBUG] Using database URL: {debug_url}")
    if connect_args:
        print(f"[DEBUG] SSL connect args: {connect_args}")

# Create async engine with SSL configuration
# Enable pool_pre_ping so stale/closed connections are detected and refreshed,
# which helps avoid "connection is closed" errors with Neon after idle periods.
engine = create_async_engine(
    database_url,
    connect_args=connect_args if connect_args else None,
    echo=True,  # Set to False in production
    future=True,
    pool_pre_ping=True,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()


class CustomerData(Base):
    """Customer data table with all specified columns."""
    __tablename__ = "customer_data"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Customer identification
    agreement_no = Column(String(255), nullable=True, index=True)
    customer_name = Column(String(255), nullable=True)
    contact_number = Column(String(50), nullable=True)
    
    # Organizational structure
    branch = Column(String(255), nullable=True)
    zone = Column(String(255), nullable=True)
    product = Column(String(255), nullable=True)
    state = Column(String(255), nullable=True)
    area = Column(String(255), nullable=True)
    
    # Bucket groups
    bkt_grp_may = Column(String(255), nullable=True)
    bkt_grp_june = Column(String(255), nullable=True)
    
    # Management names
    ncm_name = Column(String(255), nullable=True)
    rcm_name = Column(String(255), nullable=True)
    zcm_name = Column(String(255), nullable=True)
    am_name = Column(String(255), nullable=True)
    
    # Agency information
    agency_code = Column(String(255), nullable=True)
    agency_name = Column(String(255), nullable=True)
    roll = Column(String(255), nullable=True)
    
    # Dealer information
    dealer_name = Column(String(255), nullable=True)
    
    # Asset information
    asset = Column(String(255), nullable=True)
    registration_no = Column(String(255), nullable=True)
    
    # Repo information
    repo_status = Column(String(255), nullable=True)
    repo_intimation_date = Column(Date, nullable=True)
    settlement_done_or_not = Column(Boolean, nullable=True)
    
    # Payment information
    receipt_date = Column(Date, nullable=True)
    deposition_date = Column(Date, nullable=True)
    payment_amt = Column(Numeric(15, 2), nullable=True)
    
    # EMI
    emi = Column(Numeric(15, 2), nullable=True)


async def get_db() -> AsyncSession:
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database - create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections."""
    await engine.dispose()

