import { useState } from 'react';
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

export default function BrokerSetup({ data, updateData, onNext, onPrevious }: BrokerSetupProps) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    updateData({ [e.target.name]: e.target.value });
  };
  
  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    let isValid = true;
    // Validation
    if (brokerType === '1') {
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
    setErrors(newErrors);
    return isValid;
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
  console.log('showBrokerDetails:', showBrokerDetails);
  console.log('brokerType:', brokerType);
  
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
        
        {brokerType === 'container' && (
          <div className="p-4 bg-blue-50 rounded-md">
            <p className="text-sm text-blue-800">
              A new local Solace PubSub+ broker container will be created using Docker or Podman.
              The default parameters will be used.
            </p>
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
        >
          Previous
        </Button>
        <Button 
          onClick={handleSubmit}
          type="submit"
        >
          Next
        </Button>
      </div>
    </form>
  );
}