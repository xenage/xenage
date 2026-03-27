import { describe, expect, it } from "vitest";
import { iconNameForItem } from "./Icon";

describe("iconNameForItem", () => {
  it("maps RBAC kinds to distinct icons", () => {
    expect(iconNameForItem("User")).toBe("user");
    expect(iconNameForItem("Role")).toBe("role");
    expect(iconNameForItem("RoleBinding")).toBe("roleBinding");
  });
});
