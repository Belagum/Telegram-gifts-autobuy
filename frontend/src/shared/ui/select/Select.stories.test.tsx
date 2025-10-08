// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import { render } from "@testing-library/react";
import { Select } from "./Select";
import * as stories from "./Select.stories";

describe("Select stories", () => {
  it("renders default select", () => {
    const { container } = render(
      <Select {...(stories.Default.args ?? {})} options={stories.Default.args?.options ?? []} />,
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it("renders error select", () => {
    const { container } = render(
      <Select {...(stories.WithError.args ?? {})} options={stories.WithError.args?.options ?? []} />,
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});
