// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import { render } from "@testing-library/react";
import { Button } from "./Button";
import * as stories from "./Button.stories";

describe("Button stories", () => {
  it("renders primary button", () => {
    const { container } = render(<Button {...(stories.Primary.args ?? {})}>Кнопка</Button>);
    expect(container.firstChild).toMatchSnapshot();
  });

  it("renders loading state", () => {
    const { container } = render(
      <Button {...(stories.Loading.args ?? {})}>Загрузка</Button>,
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});
