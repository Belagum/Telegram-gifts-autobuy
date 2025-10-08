// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import type { ReactNode } from "react";
import React from "react";
import "./form-field.css";

export interface FormFieldProps {
  label: string;
  description?: ReactNode;
  error?: string;
  children: ReactNode;
  required?: boolean;
}

export const FormField: React.FC<FormFieldProps> = ({
  label,
  description,
  error,
  children,
  required,
}) => {
  return (
    <label className="form-field">
      <span className="form-field__label">
        {label}
        {required && <span className="form-field__required">*</span>}
      </span>
      <div className="form-field__control">{children}</div>
      {description && <div className="form-field__description">{description}</div>}
      {error && <div className="form-field__error">{error}</div>}
    </label>
  );
};
