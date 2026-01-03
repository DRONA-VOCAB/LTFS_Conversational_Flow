from sqlalchemy import create_engine, Column, Integer, String, Date, Boolean, Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class CustomerData(Base):
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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

