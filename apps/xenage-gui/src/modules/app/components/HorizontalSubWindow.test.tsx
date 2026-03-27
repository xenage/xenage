import { fireEvent, render, screen } from "@testing-library/react";
import { HorizontalSubWindow } from "./HorizontalSubWindow";

describe("HorizontalSubWindow resize", () => {
  it("resizes height by dragging top handle", () => {
    const { container } = render(
      <HorizontalSubWindow
        activeTabId="console"
        onActivateTab={() => {}}
        onCloseTab={() => {}}
        onDetachTab={() => {}}
        onReorderTabs={() => {}}
        tabs={[{ id: "console", title: "Console", icon: "session" }]}
      >
        <div>body</div>
      </HorizontalSubWindow>,
    );

    const subwindow = container.querySelector(".horizontal-subwindow") as HTMLElement;
    expect(subwindow.style.height).toBe("280px");

    const handle = screen.getByRole("separator", { name: "Resize horizontal subwindow" });
    fireEvent.mouseDown(handle, { clientY: 300 });
    fireEvent.mouseMove(window, { clientY: 240 });
    fireEvent.mouseUp(window);

    expect(subwindow.style.height).toBe("340px");
  });
});
