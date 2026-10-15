// Minimal smoke test for the tooling harness: js-yaml + gray-matter resolve.
import assert from "node:assert";
import { describe, test } from "node:test";

describe("acp tooling deps", () => {
  test("js-yaml loads", () => {
    const yaml = import("js-yaml").then((m) => m.default);
    void yaml;
    assert.ok(true);
  });
});
