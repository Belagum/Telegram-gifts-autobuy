// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import type { ReactNode } from "react";
import React from "react";
import "./table.css";

export interface TableColumn<T> {
  header: ReactNode;
  accessor: (row: T) => ReactNode;
  key: string;
}

export interface TableProps<T> {
  columns: TableColumn<T>[];
  data: T[];
  emptyState?: ReactNode;
}

export function Table<T>({ columns, data, emptyState }: TableProps<T>) {
  if (data.length === 0) {
    return <div className="ui-table__empty">{emptyState ?? "Нет данных"}</div>;
  }
  return (
    <div className="ui-table__wrapper">
      <table className="ui-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key}>{column.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {columns.map((column) => (
                <td key={column.key}>{column.accessor(row)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
