import React, { useState, useEffect, useRef } from 'react';
import { Copy, Check } from 'lucide-react';
import { Button } from '@/lib/components/ui';
import { cn } from '@/lib/utils';
import { useChatContext } from '@/lib/hooks';
import type { MessageFE, TextPart } from '@/lib/types';
import { TTSButton } from './TTSButton';

interface MessageHoverButtonsProps {
  message: MessageFE;
  className?: string;
}

export const MessageHoverButtons: React.FC<MessageHoverButtonsProps> = ({
  message,
  className
}) => {
  const { addNotification } = useChatContext();
  const [isCopied, setIsCopied] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Extract text content from message parts
  const getTextContent = (): string => {
    if (!message.parts || message.parts.length === 0) {
      return '';
    }
    const textParts = message.parts.filter(p => p.kind === "text") as TextPart[];
    return textParts.map(p => p.text).join("");
  };

  // Copy functionality
  const handleCopy = () => {
    const text = getTextContent();
    if (text.trim()) {
      navigator.clipboard.writeText(text.trim()).then(() => {
        setIsCopied(true);
        addNotification("Message copied to clipboard!", "success");
      }).catch(err => {
        console.error('Failed to copy text:', err);
        addNotification("Failed to copy message to clipboard", "error");
      });
    } else {
      addNotification("No text content to copy", "info");
    }
  };

  // Reset copied state after 2 seconds
  useEffect(() => {
    if (isCopied) {
      const timer = setTimeout(() => setIsCopied(false), 2000);
      return () => clearTimeout(timer);
    }
  }, [isCopied]);

  // Add keyboard shortcut for copy (Ctrl+Shift+C)
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Check for Ctrl+Shift+C
      if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === 'c') {
        event.preventDefault();
        handleCopy();
        
        // Flash the button to provide visual feedback
        if (buttonRef.current) {
          buttonRef.current.classList.add('bg-gray-100', 'dark:bg-gray-700');
          setTimeout(() => {
            buttonRef.current?.classList.remove('bg-gray-100', 'dark:bg-gray-700');
          }, 200);
        }
      }
    };
    
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  // Don't show buttons for status messages
  if (message.isStatusBubble || message.isStatusMessage) {
    return null;
  }

  return (
    <div className={cn(
      "flex justify-start gap-1 text-gray-500",
      className
    )}>
      {/* TTS Button - for AI messages */}
      {!message.isUser && <TTSButton message={message} />}

      {/* Copy button - all messages */}
      <Button
        ref={buttonRef}
        variant="ghost"
        size="icon"
        className="h-8 w-8 hover:bg-gray-100 dark:hover:bg-gray-800"
        onClick={handleCopy}
        tooltip={isCopied ? "Copied!" : "Copy to clipboard"}
      >
        {isCopied ? (
          <Check className="h-4 w-4 text-green-500" />
        ) : (
          <Copy className="h-4 w-4" />
        )}
      </Button>
    </div>
  );
};