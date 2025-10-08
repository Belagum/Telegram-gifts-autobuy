// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import type { CSSProperties } from "react";
import React from "react";
import clsx from "clsx";
import "./skeleton.css";

export interface SkeletonProps {
  width?: number | string;
  height?: number | string;
  rounded?: boolean;
  className?: string;
  style?: CSSProperties;
}

export const Skeleton: React.FC<SkeletonProps> = ({
  width = "100%",
  height = 16,
  rounded = true,
  className,
  style,
}) => {
  return (
    <div
      className={clsx("ui-skeleton", className, { "ui-skeleton--rounded": rounded })}
      style={{ width, height, ...style }}
      aria-hidden="true"
    />
  );
};
