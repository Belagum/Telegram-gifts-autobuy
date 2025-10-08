// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import type { SelectHTMLAttributes } from "react";
import React from "react";
import clsx from "clsx";
import "./select.css";

export interface Option<T extends string | number> {
  label: string;
  value: T;
}

export interface SelectProps<T extends string | number> extends SelectHTMLAttributes<HTMLSelectElement> {
  options: Option<T>[];
  error?: string;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps<string | number>>(
  ({ className, options, error, ...rest }, ref) => {
    return (
      <div className={clsx("ui-select", { "ui-select--error": Boolean(error) })}>
        <select ref={ref} className={clsx("ui-select__field", className)} {...rest}>
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {error && <div className="ui-select__error">{error}</div>}
      </div>
    );
  },
);

Select.displayName = "Select";
