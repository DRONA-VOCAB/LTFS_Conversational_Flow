import React, { useState } from 'react';
import './CustomerList.css';

const CustomerList = ({ customers, onSelect, loading }) => {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredCustomers = customers.filter(customer =>
    customer.customer_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    customer.contact_number?.includes(searchTerm) ||
    customer.agreement_no?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading && customers.length === 0) {
    return (
      <div className="customer-list-container">
        <div className="loading">Loading customers...</div>
      </div>
    );
  }

  return (
    <div className="customer-list-container">
      <div className="search-bar">
        <input
          type="text"
          placeholder="Search by name, phone, or agreement number..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input"
        />
      </div>

      <div className="customer-list">
        {filteredCustomers.length === 0 ? (
          <div className="no-results">
            {searchTerm ? 'No customers found matching your search.' : 'No customers available.'}
          </div>
        ) : (
          filteredCustomers.map((customer) => (
            <div key={customer.id} className="customer-card">
              <div className="customer-info">
                <h3>{customer.customer_name || 'N/A'}</h3>
                <div className="customer-details">
                  <p><strong>Phone:</strong> {customer.contact_number || 'N/A'}</p>
                  <p><strong>Agreement No:</strong> {customer.agreement_no || 'N/A'}</p>
                  <p><strong>Product:</strong> {customer.product || 'N/A'}</p>
                  <p><strong>Branch:</strong> {customer.branch || 'N/A'}</p>
                  <p><strong>State:</strong> {customer.state || 'N/A'}</p>
                </div>
              </div>
              <button
                onClick={() => onSelect(customer)}
                disabled={loading}
                className="call-button"
              >
                {loading ? 'Starting...' : 'Start Call'}
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default CustomerList;

