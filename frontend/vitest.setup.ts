// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});
