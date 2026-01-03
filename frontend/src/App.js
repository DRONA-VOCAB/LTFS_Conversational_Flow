import React, { useState, useEffect } from 'react';
import axios from 'axios';
import CustomerList from './components/CustomerList';
import CallInterface from './components/CallInterface';
import './App.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function App() {
  const [customers, setCustomers] = useState([]);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchCustomers();
  }, []);

  const fetchCustomers = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_BASE_URL}/api/customers`);
      setCustomers(response.data);
    } catch (err) {
      setError('Failed to fetch customers. Please try again.');
      console.error('Error fetching customers:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCustomerSelect = async (customer) => {
    try {
      setLoading(true);
      setError(null);
      const response = await axios.post(`${API_BASE_URL}/api/call/start/${customer.id}`);
      setSessionId(response.data.session_id);
      setSelectedCustomer(customer);
    } catch (err) {
      setError('Failed to start call. Please try again.');
      console.error('Error starting call:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCallEnd = () => {
    setSelectedCustomer(null);
    setSessionId(null);
  };

  if (selectedCustomer && sessionId) {
    return (
      <CallInterface
        sessionId={sessionId}
        customer={selectedCustomer}
        onCallEnd={handleCallEnd}
        apiBaseUrl={API_BASE_URL}
      />
    );
  }

  return (
    <div className="App">
      <div className="container">
        <header className="app-header">
          <h1>L&T Finance Voice Feedback System</h1>
          <p>Select a customer to start a feedback call</p>
        </header>
        
        {error && (
          <div className="error-message">
            {error}
            <button onClick={() => setError(null)}>Dismiss</button>
          </div>
        )}

        <CustomerList
          customers={customers}
          onSelect={handleCustomerSelect}
          loading={loading}
        />
      </div>
    </div>
  );
}

export default App;

