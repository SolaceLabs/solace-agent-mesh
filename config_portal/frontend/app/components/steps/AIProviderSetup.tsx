import { useState } from 'react';
import FormField from '../ui/FormField';
import Input from '../ui/Input';
import Button from '../ui/Button';
import ConfirmationModal from '../ui/ConfirmationModal';

type AIProviderSetupProps = {
  data: { 
    llm_endpoint_url: string;
    llm_api_key: string;
    llm_model_name: string;
    embedding_endpoint_url: string;
    embedding_api_key: string;
    embedding_model_name: string;
    [key: string]: any 
  };
  updateData: (data: Record<string, any>) => void;
  onNext: () => void;
  onPrevious: () => void;
};

export default function AIProviderSetup({ data, updateData, onNext, onPrevious }: AIProviderSetupProps) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isTestingConfig, setIsTestingConfig] = useState<boolean>(false);
  const [testError, setTestError] = useState<string | null>(null);
  const [showTestErrorDialog, setShowTestErrorDialog] = useState<boolean>(false);
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    updateData({ [e.target.name]: e.target.value });
  };
  
  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    let isValid = true;
    
    if (!data.llm_endpoint_url) {
      newErrors.llm_endpoint_url = 'LLM endpoint is required';
      isValid = false;
    }
    
    if (!data.llm_model_name) {
      newErrors.llm_model_name = 'LLM model name is required';
      isValid = false;
    }

    if(!data.llm_api_key) {
      newErrors.llm_api_key = 'LLM API key is required';
      isValid = false;
    }
    
    if (!data.embedding_endpoint_url) {
      newErrors.embedding_endpoint_url = 'Embedding endpoint is required';
      isValid = false;
    }
    
    if (!data.embedding_model_name) {
      newErrors.embedding_model_name = 'Embedding model name is required';
      isValid = false;
    }

    if(!data.embedding_api_key) {
      newErrors.embedding_api_key = 'Embedding API key is required';
      isValid = false;
    }
    
    // Check for valid model format
    if (data.llm_model_name && !data.llm_model_name.includes('/')) {
      newErrors.llm_model_name = 'Model name should follow the format provider/model-name';
      isValid = false;
    }
    
    if (data.embedding_model_name && !data.embedding_model_name.includes('/')) {
      newErrors.embedding_model_name = 'Model name should follow the format provider/model-name';
      isValid = false;
    }
    
    setErrors(newErrors);
    return isValid;
  };
  
  const testLLMConfig = async () => {
    setIsTestingConfig(true);
    setTestError(null);
    
    try {
      const response = await fetch('/api/test_llm_config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: data.llm_model_name,
          api_key: data.llm_api_key,
          base_url: data.llm_endpoint_url,
        }),
      });
      
      const result = await response.json();
      
      if (result.status === 'success') {
        // Test passed, proceed to next step
        setIsTestingConfig(false);
        onNext();
      } else {
        // Test failed, show error dialog
        setTestError(result.message || 'Failed to test LLM configuration');
        setShowTestErrorDialog(true);
        setIsTestingConfig(false);
      }
    } catch (error) {
      // Handle network or other errors
      setTestError('An error occurred while testing the LLM configuration');
      setShowTestErrorDialog(true);
      setIsTestingConfig(false);
    }
  };
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validateForm()) {
      testLLMConfig();
    }
  };
  
  return (
    <form onSubmit={handleSubmit}>
      <div className="space-y-6 ">
        <div className="p-4 bg-blue-50 rounded-md mb-4">
          <p className="text-sm text-blue-800">
            Configure your AI service providers for language models and embeddings.
            The model names should follow the format <strong>provider/model-name</strong>.
          </p>
        </div>
        
        <div className="border-b border-gray-200 pb-4 mb-4 ">
          <h3 className="text-lg font-medium mb-4 text-gray-700 font-semibold">Language Model Configuration</h3>
          
          <FormField 
            label="LLM Endpoint URL" 
            htmlFor="llm_endpoint_url"
            error={errors.llm_endpoint_url}
            required
          >
            <Input
              id="llm_endpoint_url"
              name="llm_endpoint_url"
              value={data.llm_endpoint_url}
              onChange={handleChange}
              placeholder="https://api.example.com/v1"
              autoFocus={true}
            />
          </FormField>
          
          <FormField 
            label="LLM API Key" 
            htmlFor="llm_api_key"
            error={errors.llm_api_key}
            required
          >
            <Input
              id="llm_api_key"
              name="llm_api_key"
              type="password"
              value={data.llm_api_key}
              onChange={handleChange}
              placeholder="Enter your API key"
            />
          </FormField>
          
          <FormField 
            label="LLM Model Name" 
            htmlFor="llm_model_name"
            helpText="Format: provider/model-name (e.g., openai/gpt-4o)"
            error={errors.llm_model_name}
            required
          >
            <Input
              id="llm_model_name"
              name="llm_model_name"
              value={data.llm_model_name}
              onChange={handleChange}
              placeholder="provider/model-name"
            />
          </FormField>
        </div>
        
        <div>
          <h3 className="text-lg font-medium mb-4 text-gray-700 font-semibold">Embedding Model Configuration</h3>
          
          <FormField 
            label="Embedding Endpoint URL" 
            htmlFor="embedding_endpoint_url"
            error={errors.embedding_endpoint_url}
            required
          >
            <Input
              id="embedding_endpoint_url"
              name="embedding_endpoint_url"
              value={data.embedding_endpoint_url}
              onChange={handleChange}
              placeholder="https://api.example.com/v1"
            />
          </FormField>
          
          <FormField 
            label="Embedding API Key" 
            htmlFor="embedding_api_key"
            error={errors.embedding_api_key}
            required
          >
            <Input
              id="embedding_api_key"
              name="embedding_api_key"
              type="password"
              value={data.embedding_api_key}
              onChange={handleChange}
              placeholder="Enter your API key"
            />
          </FormField>
          
          <FormField 
            label="Embedding Model Name" 
            htmlFor="embedding_model_name"
            helpText="Format: provider/model-name (e.g., openai/text-embedding-ada-002)"
            error={errors.embedding_model_name}
            required
          >
            <Input
              id="embedding_model_name"
              name="embedding_model_name"
              value={data.embedding_model_name}
              onChange={handleChange}
              placeholder="provider/model-name"
            />
          </FormField>
        </div>
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

      {/* Loading indicator */}
      {isTestingConfig && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full text-center">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Testing LLM Configuration</h3>
            <div className="flex justify-center mb-4">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-solace-green"></div>
            </div>
            <p>Please wait while we test your LLM configuration...</p>
          </div>
        </div>
      )}
      
      {/* Error dialog */}
      {showTestErrorDialog && (
        <ConfirmationModal
          message={`LLM Configuration Test Failed: ${testError}

This may indicate an issue with your LLM provider settings. Please check your endpoint URL, API key, and model name.

Would you like to ignore this warning and continue anyway?`}
          onConfirm={() => {
            setShowTestErrorDialog(false);
            onNext(); // Ignore the error and proceed
          }}
          onCancel={() => {
            setShowTestErrorDialog(false);
            // Stay on the current page to let the user fix the configuration
          }}
        />
      )}
    </form>
  );
}