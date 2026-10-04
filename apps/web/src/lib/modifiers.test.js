import test from "node:test";
import assert from "node:assert/strict";

import { emptyModifierRow, modifierRowFrom, buildModifierGroupPayload } from "./modifiers.js";

test("a blank row defaults to no ingredient and quantity 1", () => {
  assert.deepEqual(emptyModifierRow(), {
    name: "",
    price_delta: "0.00",
    ingredient_product_id: "",
    quantity: "1",
  });
});

test("an option with no ingredient omits the recipe from the payload", () => {
  const body = buildModifierGroupPayload({
    name: "  Milk  ",
    modifiers: [{ name: "Oat milk", price_delta: "0.50", ingredient_product_id: "", quantity: "" }],
  });
  assert.equal(body.name, "Milk");
  assert.deepEqual(body.modifiers, [
    { name: "Oat milk", price_delta: 0.5, ingredient_product_id: null, quantity: 1 },
  ]);
});

test("an option with an ingredient carries the id and integer quantity", () => {
  const body = buildModifierGroupPayload({
    name: "Milk",
    modifiers: [
      { name: "Oat milk", price_delta: "0.50", ingredient_product_id: "11111111-1111-1111-1111-111111111111", quantity: "2" },
    ],
  });
  assert.deepEqual(body.modifiers[0], {
    name: "Oat milk",
    price_delta: 0.5,
    ingredient_product_id: "11111111-1111-1111-1111-111111111111",
    quantity: 2,
  });
});

test("blank-named rows are dropped and a bad quantity falls back to 1", () => {
  const body = buildModifierGroupPayload({
    name: "Extras",
    modifiers: [
      { name: "   ", price_delta: "1.00", ingredient_product_id: "abc", quantity: "3" },
      { name: "Extra shot", price_delta: "", ingredient_product_id: "abc", quantity: "0" },
      { name: "Syrup", price_delta: "0.25", ingredient_product_id: "abc", quantity: "not-a-number" },
    ],
  });
  assert.equal(body.modifiers.length, 2);
  assert.equal(body.modifiers[0].name, "Extra shot");
  assert.equal(body.modifiers[0].quantity, 1);
  assert.equal(body.modifiers[0].price_delta, 0);
  assert.equal(body.modifiers[1].quantity, 1);
});

test("an existing modifier round-trips into an editable row", () => {
  assert.deepEqual(
    modifierRowFrom({ name: "Whole milk", price_delta: "0.00", ingredient_product_id: "abc", quantity: 1 }),
    { name: "Whole milk", price_delta: "0.00", ingredient_product_id: "abc", quantity: "1" },
  );
  assert.deepEqual(modifierRowFrom({ name: "Extra shot", price_delta: "0.50" }), {
    name: "Extra shot",
    price_delta: "0.50",
    ingredient_product_id: "",
    quantity: "1",
  });
});
