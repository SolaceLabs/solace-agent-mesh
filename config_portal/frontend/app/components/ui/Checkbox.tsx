import React from 'react';

type CheckboxProps = React.InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  labelClassName?: string;
};

const Checkbox: React.FC<CheckboxProps> = ({
  label,
  id,
  className,
  labelClassName,
  ...props
}) => {
  const generatedId = id || `checkbox-${Math.random().toString(36).substring(2, 9)}`;

  return (
    <div className={`flex items-center ${className || ''}`}>
      <input
        type="checkbox"
        id={generatedId}
        {...props}
        className={`h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 ${props.disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}
      />
      {label && (
        <label
          htmlFor={generatedId}
          className={`ml-2 block text-sm text-gray-700 ${labelClassName || ''} ${props.disabled ? 'cursor-not-allowed opacity-70' : 'cursor-pointer'}`}
        >
          {label}
        </label>
      )}
    </div>
  );
};

export default Checkbox;