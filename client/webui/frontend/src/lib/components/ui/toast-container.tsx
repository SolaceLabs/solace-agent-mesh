import { useChatContext } from "@/lib/hooks";
import { Toast } from "../toast";

export function ToastContainer() {
    const { notifications } = useChatContext();

    if (notifications.length === 0) {
        return null;
    }

    return (
        <div className="pointer-events-none fixed bottom-4 left-1/2 z-50 flex -translate-x-1/2 transform flex-col-reverse gap-2">
            {notifications.map(notification => (
                <div key={notification.id} className="pointer-events-auto">
                    <Toast id={notification.id} message={notification.message} type={notification.type} />
                </div>
            ))}
        </div>
    );
}
