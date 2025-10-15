// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import type { KeyboardEvent, ReactNode } from "react";
import React, { useEffect, useRef } from "react";
import ReactDOM from "react-dom";
import "./modal.css";

export interface ModalProps {
  open: boolean;
  title?: string;
  children: ReactNode;
  onClose: () => void;
  footer?: ReactNode;
}

const portalElement = typeof document !== "undefined" ? document.body : null;

let modalStack: number[] = [];
let nextModalId = 0;

export const Modal: React.FC<ModalProps> = ({ open, title, children, footer, onClose }) => {
  const modalIdRef = useRef<number>(nextModalId++);
  
  useEffect(() => {
    if (!portalElement) return;
    if (open) {
      portalElement.style.overflow = "hidden";
    }
    return () => {
      portalElement.style.overflow = "";
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    
    const modalId = modalIdRef.current;
    modalStack.push(modalId);
    
    return () => {
      modalStack = modalStack.filter(id => id !== modalId);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    
    const handleEscapeKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") {
        const lastModalId = modalStack[modalStack.length - 1];
        if (lastModalId === modalIdRef.current) {
          onClose();
        }
      }
    };

    document.addEventListener("keydown", handleEscapeKey);
    return () => {
      document.removeEventListener("keydown", handleEscapeKey);
    };
  }, [open, onClose]);

  if (!open || !portalElement) {
    return null;
  }

  const handleBackdropKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape" || event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onClose();
    }
  };

  return ReactDOM.createPortal(
    <div className="ui-modal" role="dialog" aria-modal="true">
      <div
        className="ui-modal__backdrop"
        role="button"
        tabIndex={0}
        aria-label="Закрыть модальное окно"
        onClick={onClose}
        onKeyDown={handleBackdropKeyDown}
      />
      <div className="ui-modal__content">
        {title && (
          <header className="ui-modal__header">
            <h2>{title}</h2>
          </header>
        )}
        <div className="ui-modal__body">{children}</div>
        {footer && <footer className="ui-modal__footer">{footer}</footer>}
      </div>
    </div>,
    portalElement,
  );
};
