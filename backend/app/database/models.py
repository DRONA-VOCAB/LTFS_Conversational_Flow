"""Database connection and session management for Neon PostgreSQL."""

import ssl
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Integer, Numeric, Date, Boolean
from  config.settings import settings


# Process database URL for asyncpg compatibility
database_url = settings.database_url

# If DATABASE_URL isn't set, fall back to a local SQLite DB to allow local development.
if not database_url:
    db_path = Path(__file__).parent.parent.parent / "data" / "app.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    database_url = f"sqlite+aiosqlite:///{db_path}"
    print(f"[INFO] No DATABASE_URL configured; falling back to SQLite DB at {db_path}")

# If using SQLite, skip the Postgres-specific validation and SSL rules
if database_url.startswith("sqlite"):
    connect_args = {}
    engine = create_async_engine(
        database_url,
        echo=False,
        future=True,
    )
else:
    # Parse URL first to validate and fix
    parsed = urlparse(database_url)

    # Validate hostname
    if not parsed.hostname:
        raise ValueError(
            f"Invalid DATABASE_URL format. Missing hostname.\n"
            f"Expected format: postgresql://user:password@host:port/database\n"
            f"Your URL: {database_url[:50]}..."
        )

    # Ensure database name is specified
    if not parsed.path or parsed.path == "/":
        raise ValueError(
            f"Invalid DATABASE_URL format. Missing database name.\n"
            f"Expected format: postgresql://user:password@host:port/database\n"
            f"Your URL ends with: {database_url[-50:]}"
        )

    # Extract and remove SSL-related query parameters BEFORE adding port
    query_params = parse_qs(parsed.query)

    # Remove sslmode and channel_binding from query params
    if "sslmode" in query_params:
        del query_params["sslmode"]
    if "channel_binding" in query_params:
        del query_params["channel_binding"]

    # Reconstruct query string without SSL params
    new_query = urlencode(query_params, doseq=True) if query_params else ""
    parsed = parsed._replace(query=new_query)

    # Ensure port is specified (default to 5432 if missing)
    if not parsed.port:
        # Reconstruct netloc with port
        if parsed.username and parsed.password:
            netloc = f"{parsed.username}:{parsed.password}@{parsed.hostname}:5432"
        elif parsed.username:
            netloc = f"{parsed.username}@{parsed.hostname}:5432"
        else:
            netloc = f"{parsed.hostname}:5432"
        parsed = parsed._replace(netloc=netloc)
        print(f"[INFO] Added default port 5432 to connection string")

    # Reconstruct the URL
    database_url = urlunparse(parsed)

    # Convert postgresql:// to postgresql+asyncpg:// if needed
    if (
        database_url.startswith("postgresql://")
        and "postgresql+asyncpg://" not in database_url
    ):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Extract SSL-related parameters for connect_args
    connect_args = {}

    # Enable SSL for Neon database (required)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = ssl_context

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
        print(f"[DEBUG] SSL enabled (required for Neon)")
        # Print hostname for debugging
        parsed_debug = urlparse(database_url)
        print(f"[DEBUG] Hostname: {parsed_debug.hostname}")
        print(f"[DEBUG] Port: {parsed_debug.port}")
        print(f"[DEBUG] Database: {parsed_debug.path.lstrip('/')}")

        # Check if using pooler and suggest direct connection if DNS fails
        if "pooler" in parsed_debug.hostname:
            print(
                f"[INFO] Using connection pooler. If you get DNS errors, try the direct connection URL from your Supabase/Neon dashboard."
            )

    engine = create_async_engine(
        database_url,
        connect_args=connect_args,
        echo=False,  # Set to True for SQL debugging
        future=True,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
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

    def to_dict(self):
        """Convert model instance to dictionary"""
        return {
            "id": self.id,
            "agreement_no": self.agreement_no,
            "customer_name": self.customer_name,
            "contact_number": self.contact_number,
            "product": self.product,  # Loan type
            "emi": float(self.emi) if self.emi else None,  # Amount
            "branch": self.branch,
            "zone": self.zone,
            "state": self.state,
            "area": self.area,
        }


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
