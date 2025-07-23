type InputProps = {
  id: string;
  name?: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  type?: "text" | "password" | "number" | "email";
  className?: string;
};

export default function Input({
  id,
  name,
  value,
  onChange,
  placeholder = "",
  required = false,
  disabled = false,
  type = "text",
  className = "",
  onKeyDown,
}: InputProps) {
  return (
    <input
      id={id}
      name={name || id}
      type={type}
      value={value}
      onChange={onChange}
      onKeyDown={onKeyDown}
      placeholder={placeholder}
      required={required}
      disabled={disabled}
      className={`
        w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm 
        focus:outline-none focus:ring-blue-500 focus:border-blue-500
        disabled:bg-gray-100 disabled:text-gray-500
        ${className}
      `}
    />
  );
}
