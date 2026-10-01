/**
 * Build audience-safe copy for a warning/error item.
 * Binds the v2 error catalog entries to raw worker messages: resolver
 * failures carry their payload in the message (details are empty), so the
 * message is parsed to harvest {resolver_human, reason_human}; signature
 * skips expose the generator; everything is sanitized.
 */
import {
  getCatalogEntry,
  interpolate,
  formatDetails,
  parseResolverMessage,
  resolverHumanName,
  reasonHumanName,
  sanitizeTechnicalDetail,
  titleCase,
  type CatalogCode,
} from "../error-catalog";
import { signatureName } from "./signature-names";

export type IssueSeverity = "critical" | "warning" | "info" | "unknown";

export interface IssueCopy {
  severity: IssueSeverity;
  title: string;
  what: string;
  action: string | null;
  detailsLine: string;
  /** Sanitized raw message for expandable "technical detail", or "". */
  technical: string;
}

export function buildIssueCopy(
  code: string,
  message: string,
  details: Record<string, unknown> | null | undefined,
  critical: boolean,
): IssueCopy {
  const entry: CatalogCode | undefined = getCatalogEntry(code);
  const severity: IssueSeverity = critical ? "critical" : (entry?.kind ?? "unknown");
  const technical = sanitizeTechnicalDetail(message);

  if (!entry) {
    return {
      severity,
      title: titleCase(code || "Unknown issue"),
      what: message || "No details available.",
      action: null,
      detailsLine: "",
      technical,
    };
  }

  // Enrich interpolation details with values parsed from the message.
  const enriched: Record<string, unknown> = { ...(details ?? {}) };

  if (code === "identifier_resolver_failed") {
    const parsed = parseResolverMessage(message || "");
    enriched.resolver_human = resolverHumanName(parsed.resolver);
    enriched.generator_human = parsed.generator ? signatureName(parsed.generator) : "";
    enriched.reason_human = reasonHumanName(parsed.error, entry.raw_error_map);
  } else if (code === "signature_generator_failed") {
    const gen = (message || "").split(":")[0]?.trim() ?? "";
    enriched.generator_human = gen ? signatureName(gen) : "requested";
  }

  return {
    severity,
    title: entry.user_title,
    what: interpolate(entry.user_what, enriched),
    action: entry.user_action ? interpolate(entry.user_action, enriched) : null,
    detailsLine: formatDetails(entry, enriched),
    technical,
  };
}
