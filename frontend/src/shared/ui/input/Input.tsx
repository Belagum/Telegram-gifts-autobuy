// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import type { InputHTMLAttributes } from "react";
import React from "react";
import clsx from "clsx";
import "./input.css";

export interface InputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "prefix" | "suffix"> {
  error?: string;
  leadingAddon?: React.ReactNode;
  trailingAddon?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, error, leadingAddon, trailingAddon, ...rest }, ref) => {
    return (
      <div className={clsx("ui-input", { "ui-input--error": Boolean(error) })}>
        {leadingAddon && <span className="ui-input__prefix">{leadingAddon}</span>}
        <input ref={ref} className={clsx("ui-input__field", className)} {...rest} />
        {trailingAddon && <span className="ui-input__suffix">{trailingAddon}</span>}
        {error && <div className="ui-input__error">{error}</div>}
      </div>
    );
  },
);

Input.displayName = "Input";
