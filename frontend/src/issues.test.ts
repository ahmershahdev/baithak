import { expect, test } from "vitest";

import { dueText, isClosed, labelClass } from "./issues";

test("dueText counts days from today", () => {
  const today = new Date(2026, 10, 22, 15, 30);
  expect(dueText("2026-11-22", today)).toBe("Due today");
  expect(dueText("2026-11-21", today)).toBe("Overdue by 1 day");
  expect(dueText("2026-11-19", today)).toBe("Overdue by 3 days");
  expect(dueText("2026-12-01", today)).toBe("Due Dec 1");
});

test("closed statuses and label colors", () => {
  expect([isClosed("done"), isClosed("canceled"), isClosed("todo")]).toEqual([true, true, false]);
  expect(labelClass("danger")).toBe("bg-danger-soft text-danger-soft-text");
});
