import { ReactNode } from "react";

type InfoBoxProps = {
  children: ReactNode;
  className?: string;
};

export function InfoBox({ children, className = "" }: InfoBoxProps) {
  return (
    <div className={`p-4 bg-blue-50 rounded-md ${className}`}>
      <p className="text-sm text-blue-800">{children}</p>
    </div>
  );
}

export function WarningBox({ children, className = "" }: InfoBoxProps) {
  return (
    <div className={`p-4 bg-yellow-50 rounded-md ${className}`}>
      <p className="text-sm text-yellow-800">{children}</p>
    </div>
  );
}

export function StatusBox({
  children,
  variant = "info",
  className = "",
}: {
  children: ReactNode;
  variant?: "info" | "success" | "error" | "loading";
  className?: string;
}) {
  const variantClasses = {
    info: "bg-blue-50 text-blue-800",
    success: "bg-green-50 text-green-800",
    error: "bg-red-50 text-red-800",
    loading: "bg-blue-50 text-blue-800",
  };

  return (
    <div className={`p-3 rounded-md ${variantClasses[variant]} ${className}`}>
      <p className="text-sm">{children}</p>
    </div>
  );
}
