/**
 * Database link builder with defensive client-side fixes.
 *
 * Mirrors the API-side fix: strip PDB `_CHAIN` suffix, prepend CHEMBL prefix.
 */

export interface LinkInput {
  identifier?: string | null;
  ident_type?: string | null;
  database_url?: string | null;
}

const BASE_URLS = {
  pdb: "https://www.rcsb.org/structure/",
  uniprot: "https://www.uniprot.org/uniprotkb/",
  alphafold: "https://alphafold.ebi.ac.uk/entry/",
  pubchem: "https://pubchem.ncbi.nlm.nih.gov/compound/",
  chembl: "https://www.ebi.ac.uk/chembl/explore/compound/",
  chebi: "https://www.ebi.ac.uk/chebi/searchId.do?chebiId=CHEBI:",
  ccd: "https://www.wwpdb.org/data/ccd/",
  alphafind: "https://alphafind.fi.muni.cz/",
} as const;

/** Strip the `_CHAIN` suffix from a PDB id (e.g. "1ABC_A" → "1ABC"). */
export function stripPdbChain(id: string): string {
  const idx = id.indexOf("_");
  return idx >= 0 ? id.slice(0, idx) : id;
}

/** Ensure a ChEMBL id starts with the "CHEMBL" prefix. */
export function ensureChemblPrefix(id: string): string {
  const upper = id.toUpperCase();
  return upper.startsWith("CHEMBL") ? upper : `CHEMBL${upper}`;
}

/**
 * Build a canonical database URL from ident_type + identifier.
 * Returns null when the ident_type is unknown.
 */
export function buildDatabaseUrl(
  identType: string | null | undefined,
  identifier: string | null | undefined,
): string | null {
  const t = (identType ?? "").toUpperCase();
  const id = (identifier ?? "").trim();
  if (!id) return null;

  switch (t) {
    case "PDB_ID":
    case "PDB":
      return `${BASE_URLS.pdb}${stripPdbChain(id).toUpperCase()}`;
    case "UNIPROT_ID":
    case "UNIPROT":
    case "UNIPROTKB":
      return `${BASE_URLS.uniprot}${id.toUpperCase()}`;
    case "CHEMBL_ID":
    case "CHEMBL":
      return `${BASE_URLS.chembl}${ensureChemblPrefix(id)}`;
    case "CHEBI_ID":
    case "CHEBI":
      return `${BASE_URLS.chebi}${ensureChemblPrefix(id).replace("CHEMBL", "CHEBI")}`;
    case "ALPHAFOLD_ID":
    case "ALPHAFOLD":
      return `${BASE_URLS.alphafold}${id.toUpperCase()}`;
    case "PUBCHEM_CID":
    case "PUBCHEM":
    case "CID":
      return `${BASE_URLS.pubchem}${id}`;
    case "CCD_ID":
    case "CCD":
      return `${BASE_URLS.ccd}${id.toUpperCase()}`;
    case "ALPHAFIND_ID":
    case "ALPHAFIND":
      return `${BASE_URLS.alphafind}${id}`;
    default:
      return null;
  }
}

/**
 * Defensively fix a database_url that may still contain the PDB `_CHAIN`
 * suffix or a bare (unprefixed) ChEMBL id.
 */
export function fixDatabaseUrl(url: string): string {
  // PDB: rcsb.org/structure/1ABC_A → rcsb.org/structure/1ABC
  url = url.replace(
    /(rcsb\.org\/structure\/)([A-Za-z0-9]+?)(_[A-Za-z0-9]+)(?=[/?#]|$)/,
    (_m, prefix, id) => `${prefix}${id.toUpperCase()}`,
  );
  // ChEMBL: .../compound/4303682 → .../compound/CHEMBL4303682
  url = url.replace(
    /(chembl\/explore\/compound\/)(\d+)(?=[/?#]|$)/,
    (_m, prefix, num) => `${prefix}CHEMBL${num}`,
  );
  return url;
}

/**
 * Resolve the best URL for a verified/identifier hit.
 * Prefers a freshly built URL from ident_type + identifier;
 * falls back to the provided database_url (defensively fixed).
 */
export function resolveHitUrl(hit: LinkInput): string | null {
  const built = buildDatabaseUrl(hit.ident_type, hit.identifier);
  if (built) return built;
  if (hit.database_url) return fixDatabaseUrl(hit.database_url);
  return null;
}
