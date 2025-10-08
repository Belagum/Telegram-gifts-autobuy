// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

import React from "react";

export const useOnScreen = (ref: React.RefObject<Element>, rootMargin = "0px"): boolean => {
  const [isIntersecting, setIntersecting] = React.useState(false);

  React.useEffect(() => {
    const element = ref.current;
    if (!element) {
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => setIntersecting(entry.isIntersecting),
      { rootMargin, threshold: 0.01 },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref, rootMargin]);

  return isIntersecting;
};
