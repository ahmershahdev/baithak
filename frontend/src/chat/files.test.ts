import { expect, test } from "vitest";

import { fileProblem, fitWithin, formatSize, MAX_FILE_SIZE } from "./files";

test("formatSize", () => {
  expect([formatSize(512), formatSize(2048), formatSize(5 * 1024 * 1024)]).toEqual([
    "512 B",
    "2 KB",
    "5.0 MB",
  ]);
});

test("fileProblem", () => {
  expect(fileProblem({ size: 10 })).toBeNull();
  expect(fileProblem({ size: 0 })).toBe("The file is empty.");
  expect(fileProblem({ size: MAX_FILE_SIZE + 1 })).toBe("Files can be up to 25 MB.");
});

test("fitWithin keeps the shape and never enlarges", () => {
  expect(fitWithin(1600, 900, 320)).toEqual({ width: 320, height: 180 });
  expect(fitWithin(100, 50, 320)).toEqual({ width: 100, height: 50 });
  expect(fitWithin(null, 50, 320)).toBeNull();
});
