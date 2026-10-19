import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

function Menu() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger>Open</DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuItem>Item</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ControlledMenu() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <span>{open ? "controlled open" : "controlled closed"}</span>
      <DropdownMenu open={open} onOpenChange={setOpen}>
        <DropdownMenuTrigger>Open</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem>Item</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );
}

const touchDown = (element: Element) =>
  fireEvent.pointerDown(element, { button: 0, ctrlKey: false, pointerType: "touch" });

describe("DropdownMenuTrigger", () => {
  it("does not open when a touch goes down, so a scroll gesture leaves it closed", () => {
    render(<Menu />);
    const trigger = screen.getByRole("button", { name: "Open" });

    touchDown(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("opens on the click that completes a touch tap", () => {
    render(<Menu />);
    const trigger = screen.getByRole("button", { name: "Open" });

    touchDown(trigger);
    fireEvent.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("menuitem", { name: "Item" })).toBeInTheDocument();
  });

  it("keeps mouse and keyboard opening", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<Menu />);
    await user.click(screen.getByRole("button", { name: "Open" }));
    expect(screen.getByRole("menuitem", { name: "Item" })).toBeInTheDocument();
    unmount();

    render(<Menu />);
    screen.getByRole("button", { name: "Open" }).focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("menuitem", { name: "Item" })).toBeInTheDocument();
  });

  it("toggles controlled menus on tap", () => {
    render(<ControlledMenu />);
    const trigger = screen.getByRole("button", { name: "Open" });

    touchDown(trigger);
    fireEvent.click(trigger);

    expect(screen.getByText("controlled open")).toBeInTheDocument();
  });
});
