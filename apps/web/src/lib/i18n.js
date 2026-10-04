// Minimal en/km strings for the guided setup surfaces: the onboarding
// quick-questions step and the setup coach. The chosen language is shared with
// the support/help surfaces through localStorage("chmaba.support.lang"), so a
// merchant picks it once and it applies everywhere.
//
// Kept dependency-free and pure so it can be unit-tested with node:test.

export const SUPPORTED_LANGUAGES = ["en", "km"];

const STRINGS = {
  en: {
    "questions.badge": "A QUICK CHECK",
    "questions.title": "How do you run your store?",
    "questions.subtitle": "Two quick questions so we can recommend the right plan. You can change everything later.",
    "questions.stores": "How many stores will you run?",
    "questions.team": "Who sells with you?",
    "questions.optional": "Anything else you sell?",
    "questions.optionalTag": "Optional",
    "questions.back": "Back",
    "questions.continue": "Continue",
    "band.store.1": "Just one store",
    "band.store.2-5": "2–5 stores",
    "band.store.6-50": "6–50 stores",
    "band.store.50+": "More than 50 stores",
    "band.team.1": "Just me",
    "band.team.2-10": "2–10 people",
    "band.team.11-99": "11–99 people",
    "band.team.100+": "100+ people",
    "cap.unit_of_measure": "Sell by weight or volume (kg, g, l, ml)",
    "cap.serials": "Track IMEI, serial numbers or warranty",
    "cap.batches": "Track batches or expiry dates",
    "cap.tables": "Serve dine-in tables (floor plan)",
    "coach.progress": "Guided setup",
    "coach.showMe": "Show me",
    "coach.openRegister": "Open register",
    "coach.readGuide": "Read guide",
    "coach.dismiss": "Dismiss setup guide",
    "coach.doneTitle": "You are all set",
    "coach.doneBody": "Your store is ready and your first sale is done. Nice work.",
    "coach.doneDismiss": "Dismiss",
  },
  km: {
    "questions.badge": "សំណួរខ្លីៗ",
    "questions.title": "តើអ្នកប្រតិបត្តិហាងយ៉ាងដូចម្តេច?",
    "questions.subtitle": "សួរខ្លីៗពីរប្រយោគ ដើម្បីយើងណែនាំគម្រោងឲ្យសមស្រប។ អ្នកអាចកែប្រែពេលក្រោយបាន។",
    "questions.stores": "តើអ្នកនឹងបើកប៉ុន្មានហាង?",
    "questions.team": "តើនរណាលក់ជាមួយអ្នក?",
    "questions.optional": "តើអ្នកលក់អ្វីផ្សេងទៀត?",
    "questions.optionalTag": "ស្រេចចិត្ត",
    "questions.back": "ត្រឡប់ក្រោយ",
    "questions.continue": "បន្ត",
    "band.store.1": "ហាងតែមួយ",
    "band.store.2-5": "2–5 ហាង",
    "band.store.6-50": "6–50 ហាង",
    "band.store.50+": "ច្រើនជាង 50 ហាង",
    "band.team.1": "ខ្លួនខ្ញុំតែម្នាក់",
    "band.team.2-10": "2–10 នាក់",
    "band.team.11-99": "11–99 នាក់",
    "band.team.100+": "100+ នាក់",
    "cap.unit_of_measure": "លក់តាមទម្ងន់ ឬបរិមាណ (kg, g, l, ml)",
    "cap.serials": "តាមដាន IMEI លេខសេរៀល ឬការធានា",
    "cap.batches": "តាមដានឡូ ឬកាលបរិច្ឆេទផុតកំណត់",
    "cap.tables": "បម្រើតុអង្គុយក្នុងហាង (ផែនការជាន់)",
    "coach.progress": "ការដំឡើងណែនាំ",
    "coach.showMe": "បង្ហាញខ្ញុំ",
    "coach.openRegister": "បើកគ្រឿងគិតលុយ",
    "coach.readGuide": "អានការណែនាំ",
    "coach.dismiss": "បិទការណែនាំដំឡើង",
    "coach.doneTitle": "រួចរាល់ទាំងអស់",
    "coach.doneBody": "ហាងរបស់អ្នករួចរាល់ ហើយការលក់ដំបូងបានសម្រេច។ អស្ចារ្យណាស់។",
    "coach.doneDismiss": "បិទ",
  },
};

export function getStoredLanguage(fallback = "en") {
  try {
    const value = localStorage.getItem("chmaba.support.lang");
    return SUPPORTED_LANGUAGES.includes(value) ? value : fallback;
  } catch {
    return fallback;
  }
}

export function translate(key, language = "en") {
  const table = STRINGS[language] || STRINGS.en;
  return table[key] ?? STRINGS.en[key] ?? key;
}
