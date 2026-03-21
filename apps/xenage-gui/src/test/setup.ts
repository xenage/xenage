import React from "react";
import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
});

if (!window.CSS) {
  Object.defineProperty(window, "CSS", {
    value: {
      escape: (value: string) => value,
    },
    writable: true,
  });
} else if (!window.CSS.escape) {
  (window.CSS as { escape: (value: string) => string }).escape = (value: string) => value;
}

vi.mock("overlayscrollbars-react", () => {
  type OverlayProps = React.HTMLAttributes<HTMLDivElement> & {
    options?: unknown;
  };

  const OverlayScrollbarsComponent = React.forwardRef<{
    getElement: () => HTMLDivElement | null;
    osInstance: () => {
      elements: () => {
        scrollOffsetElement: HTMLDivElement | null;
      };
    };
  }, OverlayProps>(function OverlayScrollbarsComponentMock(
    { children, options: _options, ...rest },
    forwardedRef,
  ) {
    const containerRef = React.useRef<HTMLDivElement | null>(null);

    React.useImperativeHandle(
      forwardedRef,
      () => ({
        getElement: () => containerRef.current,
        osInstance: () => ({
          elements: () => ({
            scrollOffsetElement: containerRef.current,
          }),
        }),
      }),
      [],
    );

    return React.createElement("div", { ...rest, ref: containerRef }, children);
  });

  return { OverlayScrollbarsComponent };
});
