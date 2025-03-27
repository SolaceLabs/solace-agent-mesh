import { useEffect, useState } from 'react';
import FormField from '../ui/FormField';
import Input from '../ui/Input';
import Select from '../ui/Select';
import Button from '../ui/Button';

type BrokerSetupProps = {
  data: { 
    broker_type: string;
    broker_url: string;
    broker_vpn: string;
    broker_username: string;
    broker_password: string;
    container_engine?: string;
    [key: string]: any 
  };
  updateData: (data: Record<string, any>) => void;
  onNext: () => void;
  onPrevious: () => void;
};

const brokerOptions = [
  { value: 'solace', label: 'Existing Solace Pub/Sub+ broker' },
  { value: 'container', label: 'New local Solace PubSub+ broker container (podman/docker)' },
  { value: 'dev_mode', label: 'Run in \'dev mode\' - all in one process (not recommended for production)' },
];

const containerEngineOptions = [
  { value: 'podman', label: 'Podman' },
  { value: 'docker', label: 'Docker' },
];

export default function BrokerSetup({ data, updateData, onNext, onPrevious }: BrokerSetupProps) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isRunningContainer, setIsRunningContainer] = useState(false);
  const [containerStatus, setContainerStatus] = useState<{
    isRunning: boolean;
    success: boolean;
    message: string;
  }>({
    isRunning: false,
    success: false,
    message: '',
  });

  useEffect(() => {
    if (!data.container_engine && data.broker_type === 'container') {
      updateData({ container_engine: 'podman' });
    }
    if (data.container_engine && data.broker_type !== 'container') {
      updateData({ container_engine: '' });
    }

    if (data.broker_type === 'container' && data.container_engine) {

      setContainerStatus({
        isRunning: false,
        success: true,
        message: 'Container already started'
       });
    }

    // Set dev_mode to false if it's not the selected broker type
    if (data.broker_type !== 'dev_mode') {
      updateData({ dev_mode: false });
    } else if (data.broker_type === 'dev_mode') {
      updateData({ dev_mode: true });
    }
    
  }, [data.broker_type]);
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    updateData({ [e.target.name]: e.target.value });
  };
  
  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    let isValid = true;
    
    // Validation for existing broker
    if (brokerType === 'solace') {
      if (!data.broker_url) {
        newErrors.broker_url = 'Broker URL is required';
        isValid = false;
      }
      if (!data.broker_vpn) {
        newErrors.broker_vpn = 'VPN name is required';
        isValid = false;
      }
      if (!data.broker_username) {
        newErrors.broker_username = 'Username is required';
        isValid = false;
      }
      if (!data.broker_password) {
        newErrors.broker_password = 'Password is required';
        isValid = false;
      }
    }
    
    // Validation for container - ensure container has been successfully started
    if (brokerType === 'container' && !containerStatus.success) {
      newErrors.container = 'You must successfully run the container before proceeding';
      isValid = false;
    }
    
    setErrors(newErrors);
    return isValid;
  };
  
  const handleRunContainer = async () => {
    setIsRunningContainer(true);
    setContainerStatus({
      isRunning: true,
      success: false,
      message: 'Starting container...',
    });
    
    try {
      const response = await fetch('api/runcontainer', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          container_engine: data.container_engine
        }),
      });
      
      const result = await response.json();
      
      if (result.status === 'success') {
        setContainerStatus({
          isRunning: false,
          success: true,
          message: result.message || 'Container started successfully!'
        });
        // Update the selected container engine in case it was auto-selected
        updateData({ container_engine: data.container_engine });
      } else {
        setContainerStatus({
          isRunning: false,
          success: false,
          message: result.message || 'Failed to start container. Please try again.'
        });
      }
    } catch (error) {
      setContainerStatus({
        isRunning: false,
        success: false,
        message: error instanceof Error ? error.message : 'An unexpected error occurred'
      });
    } finally {
      setIsRunningContainer(false);
    }
  };
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validateForm()) {
      onNext();
    }
  };
  
  const brokerType = data.broker_type;
  
  // Show broker connection details default option
  const showBrokerDetails = brokerType === 'solace';
  const showContainerDetails = brokerType === 'container';
  
  return (
    <form onSubmit={handleSubmit}>
      <div className="space-y-6">
        <FormField 
          label="Broker Type" 
          htmlFor="broker_type"
          required
        >
          <Select
            id="broker_type"
            name="broker_type"
            options={brokerOptions}
            value={brokerType}
            onChange={handleChange}
            disabled={containerStatus.success && data.broker_type==='container'}
            required
          />
        </FormField>
        
        {showBrokerDetails && (
          <div className="space-y-4 p-4 border border-gray-200 rounded-md">
            <FormField 
              label="Broker URL" 
              htmlFor="broker_url"
              error={errors.broker_url}
              required
            >
              <Input
                id="broker_url"
                name="broker_url"
                value={data.broker_url || ''}
                onChange={handleChange}
                placeholder="ws://localhost:8008"
                required
              />
            </FormField>
            
            <FormField 
              label="VPN Name" 
              htmlFor="broker_vpn"
              error={errors.broker_vpn}
              required
            >
              <Input
                id="broker_vpn"
                name="broker_vpn"
                value={data.broker_vpn || ''}
                onChange={handleChange}
                placeholder="default"
                required
              />
            </FormField>
            
            <FormField 
              label="Username" 
              htmlFor="broker_username"
              error={errors.broker_username}
              required
            >
              <Input
                id="broker_username"
                name="broker_username"
                value={data.broker_username || ''}
                onChange={handleChange}
                placeholder="default"
                required
                autoFocus={true}
              />
            </FormField>
            
            <FormField 
              label="Password" 
              htmlFor="broker_password"
              error={errors.broker_password}
              required
            >
              <Input
                id="broker_password"
                name="broker_password"
                type="password"
                value={data.broker_password || ''}
                onChange={handleChange}
                placeholder="Enter password"
                required
              />
            </FormField>
          </div>
        )}
        
        {showContainerDetails && (
          <div className="space-y-4 p-4 border border-gray-200 rounded-md">
            <FormField 
              label="Container Engine" 
              htmlFor="container_engine"
              required
            >
              <Select
                id="container_engine"
                name="container_engine"
                options={containerEngineOptions}
                value={data.container_engine || ''}
                onChange={handleChange}
                disabled={containerStatus.isRunning || containerStatus.success}
              />
            </FormField>
            
            {errors.container && (
              <div className="text-sm text-red-600 mt-1">
                {errors.container}
              </div>
            )}
            
            {containerStatus.message && (
              <div className={`p-3 rounded-md ${
                containerStatus.isRunning ? 'bg-blue-50 text-blue-800' : 
                containerStatus.success ? 'bg-green-50 text-green-800' : 
                'bg-red-50 text-red-800'
              }`}>
                {containerStatus.message}
              </div>
            )}
            
            <div className="mt-2">
              <Button 
                onClick={handleRunContainer}
                disabled={isRunningContainer || containerStatus.success}
                variant="primary"
                type="button"
              >
                {isRunningContainer ? 'Starting Container...' : 
                 containerStatus.success ? 'Container Running ✓' : 'Run Container'}
              </Button>
            </div>
          </div>
        )}
        
        {brokerType === 'dev_mode' && (
          <div className="p-4 bg-yellow-50 rounded-md">
            <p className="text-sm text-yellow-800">
              <strong>Warning:</strong> Dev mode runs everything in a single process and is not recommended for production use.
            </p>
          </div>
        )}
      </div>
      
      <div className="mt-8 flex justify-end space-x-4">
        <Button 
          onClick={onPrevious}
          variant="outline"
          type="button"
        >
          Previous
        </Button>
        <Button 
          type='submit'
          disabled={isRunningContainer}
        >
          Next
        </Button>
      </div>
    </form>
  );
}