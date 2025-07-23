import React, { useState, KeyboardEvent } from "react";
import FormField from "./FormField";
import Input from "./Input";
import Button from "./Button";

interface ChipInputProps {
  id: string;
  label: string;
  values: string[];
  onChange: (newValues: string[]) => void;
  placeholder?: string;
  helpText?: string;
  error?: string;
  required?: boolean;
  inputButtonText?: string;
  inputPlaceholder?: string;
}

const ChipInput: React.FC<ChipInputProps> = ({
  id,
  label,
  values,
  onChange,
  placeholder,
  helpText,
  error,
  required,
  inputButtonText = "Add",
  inputPlaceholder = "Type and press Add...",
}) => {
  const [inputValue, setInputValue] = useState("");

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  };

  const handleAddItem = () => {
    if (inputValue.trim() === "") {
      return;
    }
    if (values.includes(inputValue.trim())) {
      setInputValue("");
      return;
    }
    onChange([...values, inputValue.trim()]);
    setInputValue("");
  };

  const handleRemoveItem = (itemToRemove: string) => {
    onChange(values.filter((item) => item !== itemToRemove));
  };

  const handleInputKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleAddItem();
    }
  };

  return (
    <FormField
      label={label}
      htmlFor={id}
      helpText={helpText}
      error={error}
      required={required}
    >
      <div className="flex items-center space-x-2 mb-2">
        <Input
          id={id}
          name={id}
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleInputKeyDown}
          placeholder={inputPlaceholder}
          className="flex-grow"
        />
        <Button onClick={handleAddItem} variant="secondary" type="button">
          {inputButtonText}
        </Button>
      </div>
      {values.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2 p-2 border border-gray-200 rounded-md min-h-[40px]">
          {values.map((item, index) => (
            <div
              key={index}
              className="flex items-center bg-gray-100 text-gray-700 text-sm font-medium px-3 py-1 rounded-full"
            >
              <span>{item}</span>
              <button
                type="button"
                onClick={() => handleRemoveItem(item)}
                className="ml-2 text-gray-500 hover:text-gray-700 focus:outline-none"
                aria-label={`Remove ${item}`}
              >
                &times;
              </button>
            </div>
          ))}
        </div>
      )}
      {values.length === 0 && placeholder && (
        <div className="mt-2 p-2 border border-dashed border-gray-300 rounded-md min-h-[40px] flex items-center justify-center">
          <p className="text-sm text-gray-400">{placeholder}</p>
        </div>
      )}
    </FormField>
  );
};

export default ChipInput;
