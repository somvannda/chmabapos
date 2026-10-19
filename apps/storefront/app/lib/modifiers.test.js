import test from "node:test";
import assert from "node:assert/strict";

import { addModifiersToLineKey, groupSatisfied, modifierDelta, selectionComplete, splitLineKey } from "./modifiers.js";

test("a line with no add-ons keeps the plain key", () => {
  assert.equal(addModifiersToLineKey("p1", []), "p1");
  assert.equal(addModifiersToLineKey("p1", null), "p1");
});

test("a selection is order-independent and round-trips", () => {
  const one = addModifiersToLineKey("p1:v2", ["Oat", "Extra shot"]);
  const two = addModifiersToLineKey("p1:v2", ["Extra shot", "Oat"]);
  assert.equal(one, two);
  assert.deepEqual(splitLineKey(one), { baseKey: "p1:v2", modifierNames: ["Extra shot", "Oat"] });
});

test("the same product with and without an add-on is two lines", () => {
  assert.notEqual(addModifiersToLineKey("p1", ["Oat"]), "p1");
});

test("a name containing the separator cannot forge another line", () => {
  const key = addModifiersToLineKey("p1", ['Odd ~m: name']);
  assert.deepEqual(splitLineKey(key).modifierNames, ['Odd ~m: name']);
});

test("an unreadable key resolves to a plain line, not a throw", () => {
  assert.deepEqual(splitLineKey("p1~m:not-json"), { baseKey: "p1", modifierNames: [] });
});

const menu = [
  {
    id: "g1",
    name: "Milk",
    min_select: 1,
    max_select: 1,
    is_required: true,
    modifiers: [
      { name: "Oat", price_delta: "0.50" },
      { name: "Whole", price_delta: "0.00" },
    ],
  },
];

test("the delta comes from the menu, and an unknown name adds nothing", () => {
  assert.equal(modifierDelta(menu, ["Oat"]), 0.5);
  assert.equal(modifierDelta(menu, ["Oat", "Sprinkles"]), 0.5);
  assert.equal(modifierDelta(menu, []), 0);
});

test("a required group is only satisfied once an option is chosen", () => {
  assert.equal(groupSatisfied(menu[0], []), false);
  assert.equal(groupSatisfied(menu[0], ["Whole"]), true);
  assert.equal(selectionComplete(menu, { g1: [] }), false);
  assert.equal(selectionComplete(menu, { g1: ["Oat"] }), true);
});

test("a group with no rule requires nothing", () => {
  const optional = { id: "g2", name: "Extras", min_select: 0, max_select: 2, is_required: false, modifiers: [{ name: "Shot", price_delta: "0.30" }] };
  assert.equal(groupSatisfied(optional, []), true);
});
