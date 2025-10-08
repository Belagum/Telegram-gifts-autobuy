// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import { render } from "@testing-library/react";
import { Input } from "./Input";
import * as stories from "./Input.stories";

describe("Input stories", () => {
  it("renders default input", () => {
    const { container } = render(<Input {...(stories.Default.args ?? {})} />);
    expect(container.firstChild).toMatchSnapshot();
  });

  it("renders error state", () => {
    const { container } = render(<Input {...(stories.WithError.args ?? {})} />);
    expect(container.firstChild).toMatchSnapshot();
  });
});
