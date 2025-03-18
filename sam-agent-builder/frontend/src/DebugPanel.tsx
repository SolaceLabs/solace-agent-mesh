import React, { useState } from 'react';

const DebugPanel: React.FC = () => {
  const [apiResponse, setApiResponse] = useState<string>('No response yet');
  const [loading, setLoading] = useState(false);

  const testHealthCheck = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:5002/api/health', {
        mode: 'cors'
      });
      const data = await response.json();
      setApiResponse(JSON.stringify(data, null, 2));
    } catch (error) {
      if (error instanceof Error) {
        setApiResponse(`Error: ${error.message}`);
      } else {
        setApiResponse('An unknown error occurred');
      }
    } finally {
      setLoading(false);
    }
  };

  const testCreateAgent = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:5002/api/create-agent', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: 'Test Agent',
          description: 'This is a test agent',
          apiKey: null
        }),
        mode: 'cors'
      });
      const data = await response.json();
      setApiResponse(JSON.stringify(data, null, 2));
    } catch (error) {
      if (error instanceof Error) {
        setApiResponse(`Error: ${error.message}`);
      } else {
        setApiResponse('An unknown error occurred');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ 
      padding: '20px',
      margin: '20px 0',
      backgroundColor: '#f5f5f5',
      borderRadius: '8px',
      textAlign: 'left'
    }}>
      <h3 style={{ color: '#0c2139' }}>API Debug Panel</h3>
      <div>
        <button 
          onClick={testHealthCheck}
          style={{
            padding: '8px 16px',
            margin: '0 8px 8px 0',
            backgroundColor: '#00af83',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
          disabled={loading}
        >
          Test Health Check
        </button>
        <button 
          onClick={testCreateAgent}
          style={{
            padding: '8px 16px',
            margin: '0 0 8px 0',
            backgroundColor: '#00af83',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
          disabled={loading}
        >
          Test Create Agent
        </button>
      </div>
      <div style={{ marginTop: '10px' }}>
        <h4 style={{ color: '#0c2139' }}>Response:</h4>
        <pre style={{ 
          backgroundColor: 'white',
          padding: '10px',
          borderRadius: '4px',
          overflowX: 'auto',
          maxHeight: '200px'
        }}>
          {apiResponse}
        </pre>
      </div>
    </div>
  );
};

export default DebugPanel;