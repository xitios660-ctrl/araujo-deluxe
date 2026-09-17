"use strict";

function normalizePt(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

const SPECIFIC_SERVICE = /\b(brasileiro|fox|glamour|egipcio|hibrido|manutencao|henna|brow|lamination|design simples|designer simples|fibra|molde|f1|esmaltacao|banho(?: em)? gel|blindagem)\b/i;
const NEGATED_CATEGORY = /\b(nao quero|nao e|sem|deixa|esquece)\s+(?:fazer\s+)?(?:cilios?|unhas?|sobrancelhas?)\b/i;

function explicitGenericCategory(text) {
  const normalized = normalizePt(text);
  if (!normalized || SPECIFIC_SERVICE.test(normalized) || NEGATED_CATEGORY.test(normalized)) return null;
  if (/\bcilios?\b/.test(normalized)) return "cilios";
  if (/\bunhas?\b/.test(normalized)) return "unhas";
  if (/\bsobrancelhas?\b/.test(normalized)) return "sobrancelhas";
  return null;
}

module.exports = { explicitGenericCategory, normalizePt };
