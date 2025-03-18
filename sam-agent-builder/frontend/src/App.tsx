import React, { useState } from 'react';
import './App.css';
import DebugPanel from './DebugPanel';

function App() {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [requiresApi, setRequiresApi] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [response, setResponse] = useState<{ success: boolean; message: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setResponse(null);

    try {
      const response = await fetch('http://localhost:5002/api/create-agent', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name,
          description,
          apiKey: requiresApi ? apiKey : null,
        }),
        mode: 'cors', // Specify CORS mode
      });

      const data = await response.json();
      setResponse({
        success: data.success,
        message: data.message,
      });
    } catch (error) {
      setResponse({
        success: false,
        message: 'Failed to connect to the server. Please try again.',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <img src="/solace-logo.svg" className="App-logo" alt="Solace logo" />
        <h1 className="App-title">Solace Agent Builder</h1>
        <p className="App-subtitle">Create intelligent agents with natural language</p>
      </header>

      <div className="form-container">
        <h2 className="form-title">Create a New Agent</h2>
        
        {response && (
          <div className={`response ${response.success ? 'success' : 'error'}`} style={{
            padding: '10px',
            marginBottom: '20px',
            borderRadius: '4px',
            backgroundColor: response.success ? '#e7f7ef' : '#ffeeee',
            color: response.success ? '#068f6c' : '#d32f2f',
            border: `1px solid ${response.success ? '#068f6c' : '#d32f2f'}`,
          }}>
            {response.message}
          </div>
        )}
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="name">Agent Name</label>
            <input
              id="name"
              className="form-input"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter a name for your agent"
              required
            />
          </div>
          
          <div className="form-group">
            <label className="form-label" htmlFor="description">Agent Description</label>
            <textarea
              id="description"
              className="form-input form-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe what your agent should do..."
              required
            />
          </div>
          
          <div className="form-group">
            <label className="api-toggle">
              <input
                type="checkbox"
                checked={requiresApi}
                onChange={(e) => setRequiresApi(e.target.checked)}
              />
              Requires API Key
            </label>
            
            {requiresApi && (
              <div className="form-group">
                <label className="form-label" htmlFor="apiKey">API Key</label>
                <input
                  id="apiKey"
                  className="form-input"
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Enter your API key"
                  required={requiresApi}
                />
              </div>
            )}
          </div>
          
          <button 
            className="submit-button" 
            type="submit" 
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Creating...' : 'Create Agent'}
          </button>
        </form>
        
        {/* Debug panel for development */}
        <DebugPanel />
      </div>
    </div>
  );
}

export default App;
