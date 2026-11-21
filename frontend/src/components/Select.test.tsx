import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import { Select } from "./Select";

const options = [
  { value: "admin", label: "Admin" },
  { value: "member", label: "Member" },
  { value: "guest", label: "Guest" },
];

function form(onChange = vi.fn()) {
  render(
    <form aria-label="Invite">
      <label htmlFor="role">Role</label>
      <Select id="role" name="role" defaultValue="member" options={options} onChange={onChange} />
    </form>,
  );
  return onChange;
}

const value = () =>
  new FormData(screen.getByRole<HTMLFormElement>("form", { name: "Invite" })).get("role");

describe("Select", () => {
  test("shows the chosen label and sends its value with the form", () => {
    form();

    expect(screen.getByRole("combobox", { name: "Role" })).toHaveTextContent("Member");
    expect(value()).toBe("member");
  });

  test("a click opens the list and picking an option closes it", async () => {
    const onChange = form();

    await userEvent.click(screen.getByRole("combobox", { name: "Role" }));
    expect(screen.getByRole("option", { name: "Member" })).toHaveAttribute("aria-selected", "true");
    await userEvent.click(screen.getByRole("option", { name: "Guest" }));

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(onChange).toHaveBeenCalledWith("guest");
    expect(value()).toBe("guest");
    expect(screen.getByRole("combobox")).toHaveFocus();
  });

  test("works from the keyboard: arrows, Enter, typing a letter, Escape", async () => {
    const onChange = form();
    screen.getByRole("combobox").focus();

    await userEvent.keyboard("{ArrowDown}{ArrowUp}{Enter}");
    expect(value()).toBe("admin");

    await userEvent.keyboard("{Enter}g{Enter}");
    expect(value()).toBe("guest");

    await userEvent.keyboard("{ArrowDown}{Home}{Escape}");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(value()).toBe("guest");
    expect(onChange).toHaveBeenCalledTimes(2);
  });

  test("a click outside closes the list without a change", async () => {
    const onChange = form();

    await userEvent.click(screen.getByRole("combobox"));
    await userEvent.click(document.body);

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });
});
