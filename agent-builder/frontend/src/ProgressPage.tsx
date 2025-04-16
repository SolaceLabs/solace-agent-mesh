import React, { useEffect, useState } from 'react';
import './App.css';

interface ProgressState {
  status: 'initializing' | 'in_progress' | 'completed' | 'failed';
  progress: number;
  message: string;
  error: string | null;
  is_complete?: boolean;
}

// Define steps for the progress visualization
const progressSteps = [
  { threshold: 0, label: "Hold tight, kicking things off!" },
  { threshold: 10, label: "Getting our agent warmed up..." },
  { threshold: 20, label: "Building some magic behind the scenes!" },
  { threshold: 40, label: "Almost decoded the AI's wisdom..." },
  { threshold: 60, label: "Testing the agent's new powers..." },
  { threshold: 70, label: "Agent's brain getting smarter..." },
  { threshold: 80, label: "Just tweaking some settings..." },
  { threshold: 85, label: "Wrapping up cool agent powers!" },
  { threshold: 95, label: "Quickly crafting some test magic..." },
  { threshold: 100, label: "Voilà! Your agent is ready!" }
];

function ProgressPage({ trackingId, onComplete }: { trackingId: string; onComplete: () => void }) {
  const [progress, setProgress] = useState<ProgressState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [progressHistory, setProgressHistory] = useState<{message: string, progress: number}[]>([]);
  const [streamClosed, setStreamClosed] = useState(false);

  // State for smooth progress animation
  const [displayProgress, setDisplayProgress] = useState(0);
  
  // Effect for smooth progress transition
  useEffect(() => {
    if (progress && progress.progress > displayProgress) {
      // Calculate how quickly to animate based on the difference
      const diff = progress.progress - displayProgress;
      const step = Math.max(0.5, Math.min(1, diff / 10)); // Between 0.5 and 1 based on difference
      
      // Use animation frame for smooth transition
      const timeout = setTimeout(() => {
        setDisplayProgress(prev => {
          // Move toward target, but don't exceed it
          const next = Math.min(progress.progress, prev + step);
          return next;
        });
      }, 50); // Update every 50ms for smooth animation
      
      return () => clearTimeout(timeout);
    }
  }, [progress, displayProgress]);

  useEffect(() => {
    let eventSource: EventSource | null = null;
    
    try {
      // Create an EventSource connection to the SSE endpoint
      eventSource = new EventSource(`http://localhost:5002/api/progress/${trackingId}/stream`);
      
      // Listen for open event
      eventSource.onopen = () => {
        setConnected(true);
      };
      
      // Add artificial delay between steps for better UX
      const addMessageWithDelay = (message: string, progress: number) => {
        // Avoid adding duplicate messages
        setProgressHistory(prev => {
          const exists = prev.some(item => item.message === message);
          if (!exists) {
            return [...prev, {
              message,
              progress
            }];
          }
          return prev;
        });
      };
      
      // Handle incoming events
      eventSource.onmessage = (event) => {
        try {
          const eventData = JSON.parse(event.data);
          
          // Handle different event types
          if (eventData.event === 'connected') {
            console.log('Connected to progress stream');
          } else if (eventData.event === 'progress') {
            // Update progress state with a slight delay for better UX
            const progressData = eventData.data;
            
            // Add a small delay before updating progress, staggered based on current progress
            setTimeout(() => {
              setProgress(progressData);
              
              // Add to progress history if it's a new message
              if (progressData.message) {
                addMessageWithDelay(progressData.message, progressData.progress);
              }
            }, 300); // Small delay for smoother transitions between rapid updates
          } else if (eventData.event === 'complete') {
            // Event source will be closed automatically after this event
            console.log('Progress stream completed');
            
            // Close the EventSource connection
            if (eventSource) {
              eventSource.close();
              setStreamClosed(true);
            }
          }
        } catch (err) {
          console.error('Error parsing event data:', err);
        }
      };
      
      // Handle errors
      eventSource.onerror = (err) => {
        console.error('EventSource error:', err);
        setError('Connection to server lost. Please try again.');
        
        // Close the connection on error
        if (eventSource) {
          eventSource.close();
          setStreamClosed(true);
        }
      };
    } catch (err) {
      console.error('Error setting up EventSource:', err);
      setError('Failed to connect to progress updates. Please try again.');
    }
    
    // Cleanup function
    return () => {
      if (eventSource) {
        console.log('Closing EventSource connection');
        eventSource.close();
      }
    };
  }, [trackingId, onComplete]);

  if (error) {
    return (
      <div className="progress-container error">
        <div className="progress-header">
          <h2>Error Occurred</h2>
          <p className="progress-subtitle">We encountered a problem while creating your agent</p>
        </div>
        
        <div className="error-message">
          <h3>Error Details</h3>
          <p>{error}</p>
        </div>
        
        <button onClick={onComplete} className="submit-button">
          Back to Form
        </button>
      </div>
    );
  }

  if (!connected || !progress) {
    return (
      <div className="progress-container">
        <div className="progress-header">
          <h2>Connecting to Server</h2>
          <p className="progress-subtitle">Setting up your agent creation process</p>
        </div>
        
        <div className="progress-card pulse-animation">
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `5%` }}></div>
          </div>
          <p>Establishing connection to track progress...</p>
        </div>
      </div>
    );
  }

  // Check if we're in completion state
  const isCompleted = progress.status === 'completed';
  const isFailed = progress.status === 'failed';
  
  // Handle completed view
  if (isCompleted) {
    return (
      <div className="progress-container success">
        <div className="progress-header">
          <h2>Agent Created Successfully</h2>
          <p className="progress-subtitle">
            Your Solace agent is ready to use
          </p>
        </div>
        
        <div className="success-animation">
          <svg className="checkmark" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 52 52">
            <circle className="checkmark__circle" cx="26" cy="26" r="25" fill="none"/>
            <path className="checkmark__check" fill="none" d="M14.1 27.2l7.1 7.2 16.7-16.8"/>
          </svg>
        </div>
        
        <div className="progress-card">
          <p className="progress-message">
            Your agent has been created successfully and is ready for use.
          </p>
          
          <button onClick={onComplete} className="submit-button">
            Return to Home
          </button>
        </div>
        
        {/* Optional: show completed steps */}
        <div className="progress-summary">
          <h3>Completed Steps</h3>
          <ul className="progress-steps">
            {progressHistory.map((step, index) => (
              <li key={index} className="progress-step completed">
                {step.message}
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  }
  
  // Handle failure state
  if (isFailed) {
    return (
      <div className="progress-container error">
        <div className="progress-header">
          <h2>Agent Creation Failed</h2>
          <p className="progress-subtitle">
            We encountered an error while creating your agent
          </p>
        </div>
        
        <div className="error-message">
          <h3>Error Details</h3>
          <p>{progress.error || "An unknown error occurred"}</p>
        </div>
        
        <button onClick={onComplete} className="submit-button">
          Try Again
        </button>
      </div>
    );
  }

  // Standard in-progress view
  const getStatusStyle = () => {
    if (progress.status === 'failed') return 'error';
    if (progress.status === 'completed') return 'success';
    return '';
  };
  
  // Find the current active step based on progress
  const getCurrentStep = () => {
    const currentStep = progressSteps
      .slice()
      .reverse()
      .find(step => progress && progress.progress >= step.threshold);
    
    return currentStep ? currentStep.label : "Starting";
  };

  return (
    <div className={`progress-container ${getStatusStyle()}`}>
      <div className="progress-header">
        <h2>Creating Agent</h2>
        <p className="progress-subtitle">
          Your agent is being built, please wait...
        </p>
      </div>
      
      <div className="progress-card">
        <div className="progress-bar-container">
          <div className="progress-percentage">{Math.round(displayProgress)}%</div>
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${displayProgress}%` }}
            ></div>
          </div>
        </div>
        
        <p className="progress-message">
          {getCurrentStep()}
        </p>
      </div>
      
      {/* Progress steps list */}
      {progressHistory.length > 0 && (
        <ul className="progress-steps">
          {progressHistory.map((step, index) => {
            const isActive = index === progressHistory.length - 1;
            const isCompleted = index < progressHistory.length - 1;
            
            return (
              <li 
                key={index} 
                className={`progress-step ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`}
              >
                {step.message}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default ProgressPage;