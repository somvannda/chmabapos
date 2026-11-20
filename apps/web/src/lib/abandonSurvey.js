// The one-question abandon survey shown inside the setup wizard.
//
// The prompt is opt-in: a fixed answer is one tap, "Other" is the only free
// text, and nothing is sent until the merchant chooses an answer (or presses
// Send). The rules live here rather than in the JSX so they can be tested:
//
//  - Only the five registered codes are accepted, so a typo in a component
//    cannot invent a new bucket in the admin report.
//  - "Other" is trimmed and capped at 200 characters (the server's per-value
//    cap, see app/analytics.py), and an empty answer is not an answer.
//
// See docs/onboarding-activation-analytics-plan.md (12.1) and FR-D4.

export const SURVEY_ANSWER_LIMIT = 200;

export const SURVEY_ANSWERS = [
  { code: "thinking", label: "Nothing, just thinking" },
  { code: "unclear", label: "I don't understand this step" },
  { code: "broken", label: "Something is broken" },
  { code: "expensive", label: "It's too expensive" },
  { code: "other", label: "Other" },
];

// The value to send as `answer`, or null when there is nothing worth sending.
export function surveyAnswer(code, text = "") {
  if (code === "other") {
    const trimmed = String(text ?? "").trim().slice(0, SURVEY_ANSWER_LIMIT);
    return trimmed || null;
  }
  return SURVEY_ANSWERS.some((option) => option.code === code) ? code : null;
}
