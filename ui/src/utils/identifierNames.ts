/**
 * Utility module for fetching human-readable molecule names from external databases.
 * Modeled after the old ShowVerification.tsx logic.
 */

export interface FetchedName {
  name: string;
  database_link: string | null;
}

const cache = new Map<string, FetchedName>();

/**
 * Fetch human-readable molecule name based on identifier type.
 * Results are cached to avoid redundant API calls.
 */
export async function fetchMoleculeName(type: string, id: string): Promise<FetchedName> {
  const key = `${type}:${id}`;
  if (cache.has(key)) {
    return cache.get(key)!;
  }
  
  let result: FetchedName;
  
  switch (type) {
    case "PUBCHEM_CID":
      result = await fetchPubChemCIDDetails(id);
      break;
    case "CHEMBL_ID":
      result = await fetchChEMBLDetails(id);
      break;
    case "CHEBI_ID":
      result = await fetchChEBIDetails(id);
      break;
    case "PDB_ID":
      result = await fetchPDBDetails(id);
      break;
    case "ELEMENT":
      result = fetchElementDetails(id);
      break;
    default:
      result = { name: `${id}`, database_link: null };
  }
  
  cache.set(key, result);
  return result;
}

/**
 * Fetch molecule name from PubChem by CID.
 */
async function fetchPubChemCIDDetails(id: string): Promise<FetchedName> {
  const database_link = `https://pubchem.ncbi.nlm.nih.gov/compound/${id}`;
  
  try {
    const res = await fetch(`https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/${id}/JSON/?response_type=display`);
    const data = await res.json();
    const name = data?.Record?.RecordTitle ?? `PubChem CID ${id}`;
    return { name, database_link };
  } catch {
    return { name: `PubChem CID ${id}`, database_link };
  }
}

/**
 * Fetch molecule name from ChEMBL by ID.
 */
async function fetchChEMBLDetails(id: string): Promise<FetchedName> {
  const database_link = `https://www.ebi.ac.uk/chembl/explore/compound/CHEMBL${id}`;
  
  try {
    const res = await fetch(`https://www.ebi.ac.uk/chembl/api/data/molecule/CHEMBL${id}?format=json`);
    const data = await res.json();
    const name = data?.pref_name ?? `ChEMBL ${id}`;
    return { name, database_link };
  } catch {
    return { name: `ChEMBL ${id}`, database_link };
  }
}

/**
 * Fetch molecule name from ChEBI by ID.
 */
async function fetchChEBIDetails(id: string): Promise<FetchedName> {
  const database_link = `https://www.ebi.ac.uk/chebi/searchId.do?chebiId=CHEBI:${id}`;
  
  try {
    const res = await fetch(`https://www.ebi.ac.uk/chebi/saveStructure.do?xml=true&chebiId=${id}&imageId=0`);
    const xmlText = await res.text();
    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(xmlText, "text/xml");
    const nameNode = xmlDoc.getElementsByTagName("NAME")[0];
    const name = nameNode?.textContent ?? `ChEBI ${id}`;
    return { name, database_link };
  } catch {
    return { name: `ChEBI ${id}`, database_link };
  }
}

/**
 * Fetch molecule name from PDB by ID.
 */
async function fetchPDBDetails(id: string): Promise<FetchedName> {
  // Strip chain if present
  const pdbId = id.split("_")[0].toUpperCase();
  const database_link = `https://www.rcsb.org/structure/${pdbId}`;
  
  try {
    const res = await fetch(`https://data.rcsb.org/rest/v1/core/entry/${pdbId}`);
    const data = await res.json();
    const name = data?.struct?.title ?? `PDB ${pdbId}`;
    return { name, database_link };
  } catch {
    return { name: `PDB ${pdbId}`, database_link };
  }
}

/**
 * Fetch element name from symbol.
 */
function fetchElementDetails(id: string): FetchedName {
  const symbol = id[0].toUpperCase() + id.slice(1).toLowerCase();
  
  const names: Record<string, string> = {
    H: "Hydrogen", He: "Helium", Li: "Lithium", Be: "Beryllium", B: "Boron",
    C: "Carbon", N: "Nitrogen", O: "Oxygen", F: "Fluorine", Ne: "Neon",
    Na: "Sodium", Mg: "Magnesium", Al: "Aluminium", Si: "Silicon", P: "Phosphorus",
    S: "Sulfur", Cl: "Chlorine", Ar: "Argon", K: "Potassium", Ca: "Calcium",
    Sc: "Scandium", Ti: "Titanium", V: "Vanadium", Cr: "Chromium", Mn: "Manganese",
    Fe: "Iron", Co: "Cobalt", Ni: "Nickel", Cu: "Copper", Zn: "Zinc",
    Ga: "Gallium", Ge: "Germanium", As: "Arsenic", Se: "Selenium", Br: "Bromine",
    Kr: "Krypton", Rb: "Rubidium", Sr: "Strontium", Y: "Yttrium", Zr: "Zirconium",
    Nb: "Niobium", Mo: "Molybdenum", Tc: "Technetium", Ru: "Ruthenium", Rh: "Rhodium",
    Pd: "Palladium", Ag: "Silver", Cd: "Cadmium", In: "Indium", Sn: "Tin",
    Sb: "Antimony", Te: "Tellurium", I: "Iodine", Xe: "Xenon", Cs: "Cesium",
    Ba: "Barium", La: "Lanthanum", Ce: "Cerium", Pr: "Praseodymium", Nd: "Neodymium",
    Pm: "Promethium", Sm: "Samarium", Eu: "Europium", Gd: "Gadolinium", Tb: "Terbium",
    Dy: "Dysprosium", Ho: "Holmium", Er: "Erbium", Tm: "Thulium", Yb: "Ytterbium",
    Lu: "Lutetium", Hf: "Hafnium", Ta: "Tantalum", W: "Tungsten", Re: "Rhenium",
    Os: "Osmium", Ir: "Iridium", Pt: "Platinum", Au: "Gold", Hg: "Mercury",
    Tl: "Thallium", Pb: "Lead", Bi: "Bismuth", Po: "Polonium", At: "Astatine",
    Rn: "Radon", Fr: "Francium", Ra: "Radium", Ac: "Actinium", Th: "Thorium",
    Pa: "Protactinium", U: "Uranium", Np: "Neptunium", Pu: "Plutonium", Am: "Americium",
    Cm: "Curium", Bk: "Berkelium", Cf: "Californium", Es: "Einsteinium", Fm: "Fermium",
    Md: "Mendelevium", No: "Nobelium", Lr: "Lawrencium", Rf: "Rutherfordium", Db: "Dubnium",
    Sg: "Seaborgium", Bh: "Bohrium", Hs: "Hassium", Mt: "Meitnerium", Ds: "Darmstadtium",
    Rg: "Roentgenium", Cn: "Copernicium", Nh: "Nihonium", Fl: "Flerovium", Mc: "Moscovium",
    Lv: "Livermorium", Ts: "Tennessine", Og: "Oganesson"
  };
  
  const name = names[symbol] || symbol;
  const atomicNumber = Object.keys(names).indexOf(symbol) + 1;
  const database_link = atomicNumber > 0 ? `https://pubchem.ncbi.nlm.nih.gov/element/${atomicNumber}` : null;
  
  return { name, database_link };
}
