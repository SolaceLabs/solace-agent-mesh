type ErrorAlertProps = {
  title?: string;
  message: string;
};

export default function ErrorAlert({
  title = "Error initializing project",
  message,
}: ErrorAlertProps) {
  return (
    <div className="p-4 bg-red-50 text-red-700 rounded-md border border-red-200">
      <p className="font-medium">{title}</p>
      <p>{message}</p>
    </div>
  );
}
