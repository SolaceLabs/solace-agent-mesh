/**
 * Simple email input component for when identity service is not configured.
 * Matches UserTypeahead's interface for seamless conditional rendering.
 */

import React, { useState, useRef, useEffect, useCallback } from "react";
import { cva } from "class-variance-authority";
import { X } from "lucide-react";
import { Input } from "@/lib/components/ui/input";
import { Button } from "@/lib/components/ui/button";
import { Badge } from "@/lib/components/ui/badge";
import { classForIconButton } from "./projectShareVariants";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface EmailInputProps {
    id: string;
    onSelect: (email: string, id: string) => void;
    onRemove: (id: string) => void;
    excludeEmails: string[];
    selectedEmail?: string | null;
    error?: boolean;
}

export const EmailInput: React.FC<EmailInputProps> = ({ id, onSelect, onRemove, excludeEmails, selectedEmail, error }) => {
    const [inputValue, setInputValue] = useState("");
    const [validationError, setValidationError] = useState<string | null>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        inputRef.current?.focus();
    }, []);

    const validateAndConfirm = useCallback(
        (email: string) => {
            const trimmedEmail = email.trim();

            if (!trimmedEmail) {
                setValidationError(null);
                return false;
            }

            if (!EMAIL_REGEX.test(trimmedEmail)) {
                setValidationError("Please enter a valid email address");
                return false;
            }

            if (excludeEmails.includes(trimmedEmail)) {
                setValidationError("This email has already been added");
                return false;
            }

            setValidationError(null);
            onSelect(trimmedEmail, id);
            setInputValue("");
            return true;
        },
        [excludeEmails, id, onSelect]
    );

    const handleClose = useCallback(() => {
        onRemove(id);
    }, [id, onRemove]);

    const handleKeyDown = useCallback(
        (e: React.KeyboardEvent) => {
            if (e.key === "Escape") {
                e.preventDefault();
                handleClose();
            } else if (e.key === "Enter") {
                e.preventDefault();
                validateAndConfirm(inputValue);
            }
        },
        [handleClose, inputValue, validateAndConfirm]
    );

    const handleBlur = useCallback(() => {
        if (inputValue.trim()) {
            validateAndConfirm(inputValue);
        }
    }, [inputValue, validateAndConfirm]);

    const handleInputChange = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
            const newValue = e.target.value;
            if (selectedEmail) {
                onSelect("", id);
                setInputValue(newValue);
            } else {
                setInputValue(newValue);
            }
            if (validationError) {
                setValidationError(null);
            }
        },
        [selectedEmail, onSelect, id, validationError]
    );

    const hasError = error || !!validationError;

    return (
        <>
            <div className="flex flex-col gap-1">
                <Input
                    ref={inputRef}
                    type="email"
                    autoComplete="email"
                    placeholder="Enter email address..."
                    value={selectedEmail || inputValue}
                    onChange={handleInputChange}
                    onKeyDown={handleKeyDown}
                    onBlur={handleBlur}
                    className={classForEmailInput({ error: hasError })}
                />
                {validationError && <p className="text-xs text-[var(--destructive)]">{validationError}</p>}
            </div>
            <Badge variant="secondary" className="justify-self-center">
                Viewer
            </Badge>
            <Button variant="ghost" size="sm" onClick={handleClose} className={classForIconButton()}>
                <X className="h-4 w-4" />
            </Button>
        </>
    );
};

const classForEmailInput = cva(["h-9", "pr-3"], {
    variants: {
        error: {
            true: "border-[var(--destructive)]",
            false: "",
        },
    },
    defaultVariants: { error: false },
});
