import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SchemaDataTable } from "./SchemaDataTable";

const columns = [
  { key: "name", label: "Name", width: 160 },
];

const rows = [
  { key: "row-1", values: { name: "Alpha" } },
  { key: "row-2", values: { name: "Bravo" } },
  { key: "row-3", values: { name: "Charlie" } },
  { key: "row-4", values: { name: "Delta" } },
];

function getRowCheckboxes(): HTMLInputElement[] {
  const checkboxes = screen.getAllByRole("checkbox") as HTMLInputElement[];
  return checkboxes.slice(1);
}

describe("SchemaDataTable row selection", () => {
  it("selects a visible range when shift-clicking row checkboxes", () => {
    render(<SchemaDataTable columns={columns} rows={rows} />);

    const [row1, , row3] = getRowCheckboxes();
    fireEvent.click(row1);
    fireEvent.mouseDown(row3, { shiftKey: true });
    fireEvent.mouseUp(row3, { shiftKey: true });
    fireEvent.click(row3, { shiftKey: true });

    const [selectedRow1, selectedRow2, selectedRow3, selectedRow4] = getRowCheckboxes();
    expect(selectedRow1.checked).toBe(true);
    expect(selectedRow2.checked).toBe(true);
    expect(selectedRow3.checked).toBe(true);
    expect(selectedRow4.checked).toBe(false);
  });

  it("keeps single-row behavior when shift is not pressed", () => {
    render(<SchemaDataTable columns={columns} rows={rows} />);

    const [row1, , row3] = getRowCheckboxes();
    fireEvent.click(row1);
    fireEvent.click(row3);

    const [selectedRow1, selectedRow2, selectedRow3] = getRowCheckboxes();
    expect(selectedRow1.checked).toBe(true);
    expect(selectedRow2.checked).toBe(false);
    expect(selectedRow3.checked).toBe(true);
  });
});
