import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import en from "./locales/en.json";
import he from "./locales/he.json";

export const SUPPORTED_LOCALES = ["en", "he"] as const;
export type AppLocale = (typeof SUPPORTED_LOCALES)[number];

export function isRtlLocale(locale: string): boolean {
  return locale === "he";
}

export function applyDocumentLocale(locale: AppLocale): void {
  document.documentElement.lang = locale;
  document.documentElement.dir = isRtlLocale(locale) ? "rtl" : "ltr";
  document.title = i18n.t("app.metaTitle");
  const meta = document.querySelector('meta[name="description"]');
  if (meta) meta.setAttribute("content", i18n.t("app.metaDescription"));
}

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      he: { translation: he },
    },
    fallbackLng: "en",
    supportedLngs: [...SUPPORTED_LOCALES],
    interpolation: { escapeValue: false },
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
      lookupLocalStorage: "fds-locale",
    },
  })
  .then(() => {
    applyDocumentLocale(i18n.language as AppLocale);
  });

i18n.on("languageChanged", (lng) => {
  applyDocumentLocale(lng as AppLocale);
});

export default i18n;
