import { test } from "node:test";
import assert from "node:assert/strict";

import { SURVEY_ANSWER_LIMIT, SURVEY_ANSWERS, surveyAnswer } from "./abandonSurvey.js";

test("fixed answers are the five registered codes", () => {
  assert.deepEqual(
    SURVEY_ANSWERS.map((option) => option.code),
    ["thinking", "unclear", "broken", "expensive", "other"],
  );
  for (const code of ["thinking", "unclear", "broken", "expensive"]) {
    assert.equal(surveyAnswer(code), code);
  }
});

test("an unknown code is never sent", () => {
  assert.equal(surveyAnswer("whatever"), null);
  assert.equal(surveyAnswer(""), null);
  assert.equal(surveyAnswer(undefined), null);
});

test("other is trimmed, capped and required", () => {
  assert.equal(surveyAnswer("other", "  the price is unclear  "), "the price is unclear");
  assert.equal(surveyAnswer("other", "   "), null);
  assert.equal(surveyAnswer("other", ""), null);

  const long = `x${"y".repeat(SURVEY_ANSWER_LIMIT + 50)}`;
  const answer = surveyAnswer("other", long);
  assert.equal(answer.length, SURVEY_ANSWER_LIMIT);
  assert.ok(answer.startsWith("x"));
});

test("the fixed codes ignore any text that came with them", () => {
  assert.equal(surveyAnswer("broken", "a lot of text"), "broken");
});
