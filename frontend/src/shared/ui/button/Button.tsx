// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import type { ButtonHTMLAttributes, ReactNode } from "react";
import React from "react";
import clsx from "clsx";
import "./button.css";

export type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", loading = false, disabled, className, children, icon, ...rest }, ref) => {
    const isDisabled = disabled || loading;
    return (
      <button
        ref={ref}
        className={clsx("ui-button", `ui-button--${variant}`, `ui-button--${size}`, className, {
          "ui-button--loading": loading,
        })}
        disabled={isDisabled}
        {...rest}
      >
        {icon && <span className="ui-button__icon">{icon}</span>}
        <span className="ui-button__label">{children}</span>
      </button>
    );
  },
);

Button.displayName = "Button";
