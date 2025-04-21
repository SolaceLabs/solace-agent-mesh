import { useState, useEffect } from 'react';
import FormField from '../ui/FormField';
import Input from '../ui/Input';
import Select from '../ui/Select';
import Button from '../ui/Button';
import { InfoBox, WarningBox } from '../ui/InfoBoxes';

type FileServiceSetupProps = {
  data: Record<string, any>;
  updateData: (data: Record<string, any>) => void;
  onNext: () => void;
  onPrevious: () => void;
};

const providerOptions = [
  { value: 'volume', label: 'Volume: Use a local volume (directory) to store files' },
  { value: 'bucket', label: 'Bucket: Use a cloud bucket to store files (Must use AWS S3 API)' },
];

export default function FileServiceSetup({ data, updateData, onNext, onPrevious }: FileServiceSetupProps) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [volumePath, setVolumePath] = useState('');
  const [bucketName, setBucketName] = useState('');
  const [endpointUrl, setEndpointUrl] = useState('');
  const [initialized, setInitialized] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState(data.file_service_provider || 'volume');

  // Initialize from existing data
  useEffect(() => {
    if (initialized) return;
    
    // Set the initial provider
    const initialProvider = data.file_service_provider || 'volume';
    setSelectedProvider(initialProvider);
    
    // Set initial values based on data
    if (initialProvider === 'volume') {
      let initialPath = '/tmp/solace-agent-mesh';
      
      // Parse file_service_config to extract volume path if it exists
      if (data.file_service_config && Array.isArray(data.file_service_config)) {
        const volumeConfig = data.file_service_config.find((config: string) => 
          config.startsWith('directory=')
        );
        
        if (volumeConfig) {
          initialPath = volumeConfig.split('=')[1];
        }
      }
      
      setVolumePath(initialPath);
      
      if (!data.file_service_config) {
        updateData({
          file_service_provider: initialProvider,
          file_service_config: [`directory=${initialPath}`]
        });
      }
    } else if (initialProvider === 'bucket') {
      // Parse file_service_config to extract bucket settings if they exist
      if (data.file_service_config && Array.isArray(data.file_service_config)) {
        const bucketConfig = data.file_service_config.find((config: string) => 
          config.startsWith('bucket_name=')
        );
        
        const endpointConfig = data.file_service_config.find((config: string) => 
          config.startsWith('endpoint_url=')
        );
        
        if (bucketConfig) {
          setBucketName(bucketConfig.split('=')[1]);
        }
        
        if (endpointConfig) {
          setEndpointUrl(endpointConfig.split('=')[1]);
        }
      }
    }
    
    setInitialized(true);
  }, [data, initialized, updateData]);

  const handleProviderChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newProvider = e.target.value;
    setSelectedProvider(newProvider);
    
    // Initialize default config when provider changes
    if (newProvider === 'volume') {
      const path = volumePath || '/tmp/solace-agent-mesh';
      updateData({
        file_service_provider: newProvider,
        file_service_config: [`directory=${path}`]
      });
    } else if (newProvider === 'bucket') {
      updateData({
        file_service_provider: newProvider,
        file_service_config: [
          `bucket_name=${bucketName}`,
          `endpoint_url=${endpointUrl}`
        ]
      });
    }
  };

  const handleVolumePathChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newPath = e.target.value;
    setVolumePath(newPath);
    
    updateData({ 
      file_service_config: [`directory=${newPath}`]
    });
  };

  const handleBucketNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newBucketName = e.target.value;
    setBucketName(newBucketName);
    
    updateData({
      file_service_config: [
        `bucket_name=${newBucketName}`,
        ...(endpointUrl ? [`endpoint_url=${endpointUrl}`] : [])
      ]
    });
  };

  const handleEndpointUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newEndpointUrl = e.target.value;
    setEndpointUrl(newEndpointUrl);
    
    updateData({
      file_service_config: [
        ...(bucketName ? [`bucket_name=${bucketName}`] : []),
        `endpoint_url=${newEndpointUrl}`
      ]
    });
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    let isValid = true;
    
    // Basic validation depending on provider
    if (selectedProvider === 'volume') {
      if (!volumePath) {
        newErrors.volumePath = 'Volume path is required';
        isValid = false;
      }
    } else if (selectedProvider === 'bucket') {
      if (!bucketName) {
        newErrors.bucketName = 'Bucket name is required';
        isValid = false;
      }
      if (!endpointUrl) {
        newErrors.endpointUrl = 'Endpoint URL is required';
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

  return (
    <form onSubmit={handleSubmit}>
      <div className="space-y-6">
        <InfoBox className="mb-4">
          Choose how you want to store files in your Solace Agent Mesh system.
        </InfoBox>
        
        <FormField 
          label="File Service Provider" 
          htmlFor="file_service_provider"
          required
        >
          <Select
            id="file_service_provider"
            name="file_service_provider"
            options={providerOptions}
            value={selectedProvider}
            onChange={handleProviderChange}
          />
        </FormField>
        
        {selectedProvider === 'volume' && (
          <FormField 
            label="Volume Path" 
            htmlFor="volumePath"
            helpText="The directory path where files will be stored"
            error={errors.volumePath}
            required
          >
            <Input
              id="volumePath"
              name="volumePath"
              value={volumePath}
              onChange={handleVolumePathChange}
              placeholder="/tmp/solace-agent-mesh"
              autoFocus={true}
            />
          </FormField>
        )}
        
        {selectedProvider === 'bucket' && (
          <>
            <FormField
              label="Bucket Name"
              htmlFor="bucketName"
              helpText="The name of the S3 bucket to use for file storage"
              error={errors.bucketName}
              required
            >
              <Input
                id="bucketName"
                name="bucketName"
                value={bucketName}
                onChange={handleBucketNameChange}
                placeholder="my-s3-bucket"
              />
            </FormField>
            
            <FormField
              label="Endpoint URL"
              htmlFor="endpointUrl"
              helpText="The S3 service endpoint URL"
              error={errors.endpointUrl}
              required
            >
              <Input
                id="endpointUrl"
                name="endpointUrl"
                value={endpointUrl}
                onChange={handleEndpointUrlChange}
                placeholder="https://s3.amazonaws.com"
              />
            </FormField>
            
            <WarningBox>
              <strong>Note:</strong> You can setup the Boto3 authentication configuration in the ./solace-agent-mesh.yaml file
            </WarningBox>
          </>
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
          type="submit"
        >
          Next
        </Button>
      </div>
    </form>
  );
}