import { ReactNode } from "react";

type FormFieldProps = {
  label: string;
  htmlFor: string;
  helpText?: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
};

export default function FormField({
  label,
  htmlFor,
  helpText,
  error,
  required = false,
  children,
}: FormFieldProps) {
  return (
    <div className={`mb-4`}>
      <label
        htmlFor={htmlFor}
        className="block text-sm font-medium text-gray-700 mb-1"
      >
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>
      <div className="mt-1">{children}</div>
      {helpText && <p className="mt-1 text-sm text-gray-500">{helpText}</p>}
      {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
    </div>
  );
}
