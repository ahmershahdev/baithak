import { describe, expect, test } from "vitest";

import { dayKey, dayLabel, startsDay } from "./days";

const now = new Date(2026, 10, 23, 15, 0);
const at = (year: number, month: number, day: number, hour = 9) =>
  new Date(year, month, day, hour).toISOString();

describe("dayLabel", () => {
  test("today and yesterday by name", () => {
    expect(dayLabel(at(2026, 10, 23, 0), now)).toBe("Today");
    expect(dayLabel(at(2026, 10, 22, 23), now)).toBe("Yesterday");
  });

  test("earlier this year without the year, other years with it", () => {
    expect(dayLabel(at(2026, 10, 18), now)).toBe("Wednesday, November 18");
    expect(dayLabel(at(2025, 11, 31), now)).toBe("Wednesday, December 31, 2025");
  });

  test("yesterday across a month boundary", () => {
    expect(dayLabel(at(2026, 9, 31), new Date(2026, 10, 1, 8))).toBe("Yesterday");
  });
});

describe("startsDay", () => {
  test("the first message and the first of each local day", () => {
    expect(startsDay(undefined, at(2026, 10, 23))).toBe(true);
    expect(startsDay({ created_at: at(2026, 10, 23, 8) }, at(2026, 10, 23, 20))).toBe(false);
    expect(startsDay({ created_at: at(2026, 10, 22, 23) }, at(2026, 10, 23, 0))).toBe(true);
  });

  test("dayKey is the same within a day", () => {
    expect(dayKey(at(2026, 10, 23, 1))).toBe(dayKey(at(2026, 10, 23, 22)));
  });
});
