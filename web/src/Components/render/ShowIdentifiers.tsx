// ShowIdentifiers.tsx
import { FC, useEffect, useState } from "react";
import {
    Box,
    Typography,
    Divider,
    LinearProgress,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Link,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import SegmentSelector from "../MDComponents/SegmentSelector";

interface Props {
    uuid: string;
}

interface Identifier {
    identifier_type: string;
    identifier_id: string;
    similarity: number;
}

interface IdentifierDetails {
    name: string;
    database_link: string;
    image: string;
}

const fetchPubChemCIDDetails = async (id: string): Promise<IdentifierDetails> => {
    const database_link = `https://pubchem.ncbi.nlm.nih.gov/compound/${id}`;
    const image = `https://pubchem.ncbi.nlm.nih.gov/image/imagefly.cgi?cid=${id}&width=500&height=500`;

    try {
        const res = await fetch(
            `https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/${id}/JSON/?response_type=display`
        );
        const data = await res.json();

        // Extract RecordTitle from JSON
        const name = data?.Record?.RecordTitle ?? "Unknown";

        return { name, database_link, image };
    } catch (err) {
        console.error(`Failed to fetch PubChem CID details for ${id}:`, err);
        return { name: "Unknown", database_link, image };
    }
};

const fetchChEMBLDetails = async (id: string): Promise<IdentifierDetails> => {
    const database_link = `https://www.ebi.ac.uk/chembl/explore/compound/CHEMBL${id}`;
    const image = `https://www.ebi.ac.uk/chembl/api/data/image/CHEMBL${id}.svg`;

    try {
        const res = await fetch(`https://www.ebi.ac.uk/chembl/api/data/molecule/CHEMBL${id}?format=json`);
        const data = await res.json();

        const name = data?.pref_name ?? "Unknown";

        return { name, database_link, image };
    } catch (err) {
        console.error(`Failed to fetch ChEMBL details for CHEMBL${id}:`, err);
        return { name: "Unknown", database_link, image };
    }
};

const fetchChEBIDetails = async (id: string): Promise<IdentifierDetails> => {
    const database_link = `https://www.ebi.ac.uk/chebi/searchId.do?chebiId=CHEBI:${id}`;
    const image = `https://www.ebi.ac.uk/chebi/displayImage.do?defaultImage=true&imageIndex=0&chebiId=${id}`;

    try {
        const res = await fetch(`https://www.ebi.ac.uk/chebi/saveStructure.do?xml=true&chebiId=${id}&imageId=0`);
        const xmlText = await res.text();

        // Parse XML to get NAME
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(xmlText, "text/xml");
        const nameNode = xmlDoc.getElementsByTagName("NAME")[0];
        const name = nameNode?.textContent ?? "Unknown";

        return { name, database_link, image };
    } catch (err) {
        console.error(`Failed to fetch ChEBI details for CHEBI:${id}:`, err);
        return { name: "Unknown", database_link, image };
    }
};

const fetchPDBDetails = async (id: string): Promise<IdentifierDetails> => {
    // Strip chain if present
    const pdbId = id.split("_")[0];
    const pdbIdUpper = pdbId.toUpperCase();
    const pdbIdLower = pdbId.toLowerCase();

    const database_link = `https://www.rcsb.org/structure/${pdbIdUpper}`;
    const image = `https://cdn.rcsb.org/images/structures/${pdbIdLower}_assembly-1.jpeg`;

    try {
        const res = await fetch(`https://data.rcsb.org/rest/v1/core/entry/${pdbIdUpper}`);
        const data = await res.json();
        const name = data?.struct?.title ?? "Unknown";

        return { name, database_link, image };
    } catch (err) {
        console.error(`Failed to fetch PDB details for ${id}:`, err);
        return { name: "Unknown", database_link, image };
    }
};

const ELEMENTS_TABLE: Record<string, { fullName: string; atomicId: number }> = {
    H: { fullName: "Hydrogen", atomicId: 1 },
    He: { fullName: "Helium", atomicId: 2 },
    Li: { fullName: "Lithium", atomicId: 3 },
    Be: { fullName: "Beryllium", atomicId: 4 },
    B: { fullName: "Boron", atomicId: 5 },
    C: { fullName: "Carbon", atomicId: 6 },
    N: { fullName: "Nitrogen", atomicId: 7 },
    O: { fullName: "Oxygen", atomicId: 8 },
    F: { fullName: "Fluorine", atomicId: 9 },
    Ne: { fullName: "Neon", atomicId: 10 },
    Na: { fullName: "Sodium", atomicId: 11 },
    Mg: { fullName: "Magnesium", atomicId: 12 },
    Al: { fullName: "Aluminium", atomicId: 13 },
    Si: { fullName: "Silicon", atomicId: 14 },
    P: { fullName: "Phosphorus", atomicId: 15 },
    S: { fullName: "Sulfur", atomicId: 16 },
    Cl: { fullName: "Chlorine", atomicId: 17 },
    Ar: { fullName: "Argon", atomicId: 18 },
    K: { fullName: "Potassium", atomicId: 19 },
    Ca: { fullName: "Calcium", atomicId: 20 },
    Sc: { fullName: "Scandium", atomicId: 21 },
    Ti: { fullName: "Titanium", atomicId: 22 },
    V: { fullName: "Vanadium", atomicId: 23 },
    Cr: { fullName: "Chromium", atomicId: 24 },
    Mn: { fullName: "Manganese", atomicId: 25 },
    Fe: { fullName: "Iron", atomicId: 26 },
    Co: { fullName: "Cobalt", atomicId: 27 },
    Ni: { fullName: "Nickel", atomicId: 28 },
    Cu: { fullName: "Copper", atomicId: 29 },
    Zn: { fullName: "Zinc", atomicId: 30 },
    Ga: { fullName: "Gallium", atomicId: 31 },
    Ge: { fullName: "Germanium", atomicId: 32 },
    As: { fullName: "Arsenic", atomicId: 33 },
    Se: { fullName: "Selenium", atomicId: 34 },
    Br: { fullName: "Bromine", atomicId: 35 },
    Kr: { fullName: "Krypton", atomicId: 36 },
    Rb: { fullName: "Rubidium", atomicId: 37 },
    Sr: { fullName: "Strontium", atomicId: 38 },
    Y: { fullName: "Yttrium", atomicId: 39 },
    Zr: { fullName: "Zirconium", atomicId: 40 },
    Nb: { fullName: "Niobium", atomicId: 41 },
    Mo: { fullName: "Molybdenum", atomicId: 42 },
    Tc: { fullName: "Technetium", atomicId: 43 },
    Ru: { fullName: "Ruthenium", atomicId: 44 },
    Rh: { fullName: "Rhodium", atomicId: 45 },
    Pd: { fullName: "Palladium", atomicId: 46 },
    Ag: { fullName: "Silver", atomicId: 47 },
    Cd: { fullName: "Cadmium", atomicId: 48 },
    In: { fullName: "Indium", atomicId: 49 },
    Sn: { fullName: "Tin", atomicId: 50 },
    Sb: { fullName: "Antimony", atomicId: 51 },
    Te: { fullName: "Tellurium", atomicId: 52 },
    I: { fullName: "Iodine", atomicId: 53 },
    Xe: { fullName: "Xenon", atomicId: 54 },
    Cs: { fullName: "Cesium", atomicId: 55 },
    Ba: { fullName: "Barium", atomicId: 56 },
    La: { fullName: "Lanthanum", atomicId: 57 },
    Ce: { fullName: "Cerium", atomicId: 58 },
    Pr: { fullName: "Praseodymium", atomicId: 59 },
    Nd: { fullName: "Neodymium", atomicId: 60 },
    Pm: { fullName: "Promethium", atomicId: 61 },
    Sm: { fullName: "Samarium", atomicId: 62 },
    Eu: { fullName: "Europium", atomicId: 63 },
    Gd: { fullName: "Gadolinium", atomicId: 64 },
    Tb: { fullName: "Terbium", atomicId: 65 },
    Dy: { fullName: "Dysprosium", atomicId: 66 },
    Ho: { fullName: "Holmium", atomicId: 67 },
    Er: { fullName: "Erbium", atomicId: 68 },
    Tm: { fullName: "Thulium", atomicId: 69 },
    Yb: { fullName: "Ytterbium", atomicId: 70 },
    Lu: { fullName: "Lutetium", atomicId: 71 },
    Hf: { fullName: "Hafnium", atomicId: 72 },
    Ta: { fullName: "Tantalum", atomicId: 73 },
    W: { fullName: "Tungsten", atomicId: 74 },
    Re: { fullName: "Rhenium", atomicId: 75 },
    Os: { fullName: "Osmium", atomicId: 76 },
    Ir: { fullName: "Iridium", atomicId: 77 },
    Pt: { fullName: "Platinum", atomicId: 78 },
    Au: { fullName: "Gold", atomicId: 79 },
    Hg: { fullName: "Mercury", atomicId: 80 },
    Tl: { fullName: "Thallium", atomicId: 81 },
    Pb: { fullName: "Lead", atomicId: 82 },
    Bi: { fullName: "Bismuth", atomicId: 83 },
    Po: { fullName: "Polonium", atomicId: 84 },
    At: { fullName: "Astatine", atomicId: 85 },
    Rn: { fullName: "Radon", atomicId: 86 },
    Fr: { fullName: "Francium", atomicId: 87 },
    Ra: { fullName: "Radium", atomicId: 88 },
    Ac: { fullName: "Actinium", atomicId: 89 },
    Th: { fullName: "Thorium", atomicId: 90 },
    Pa: { fullName: "Protactinium", atomicId: 91 },
    U: { fullName: "Uranium", atomicId: 92 },
    Np: { fullName: "Neptunium", atomicId: 93 },
    Pu: { fullName: "Plutonium", atomicId: 94 },
    Am: { fullName: "Americium", atomicId: 95 },
    Cm: { fullName: "Curium", atomicId: 96 },
    Bk: { fullName: "Berkelium", atomicId: 97 },
    Cf: { fullName: "Californium", atomicId: 98 },
    Es: { fullName: "Einsteinium", atomicId: 99 },
    Fm: { fullName: "Fermium", atomicId: 100 },
    Md: { fullName: "Mendelevium", atomicId: 101 },
    No: { fullName: "Nobelium", atomicId: 102 },
    Lr: { fullName: "Lawrencium", atomicId: 103 },
    Rf: { fullName: "Rutherfordium", atomicId: 104 },
    Db: { fullName: "Dubnium", atomicId: 105 },
    Sg: { fullName: "Seaborgium", atomicId: 106 },
    Bh: { fullName: "Bohrium", atomicId: 107 },
    Hs: { fullName: "Hassium", atomicId: 108 },
    Mt: { fullName: "Meitnerium", atomicId: 109 },
    Ds: { fullName: "Darmstadtium", atomicId: 110 },
    Rg: { fullName: "Roentgenium", atomicId: 111 },
    Cn: { fullName: "Copernicium", atomicId: 112 },
    Nh: { fullName: "Nihonium", atomicId: 113 },
    Fl: { fullName: "Flerovium", atomicId: 114 },
    Mc: { fullName: "Moscovium", atomicId: 115 },
    Lv: { fullName: "Livermorium", atomicId: 116 },
    Ts: { fullName: "Tennessine", atomicId: 117 },
    Og: { fullName: "Oganesson", atomicId: 118 },
};

const fetchElementDetails = async (id: string): Promise<IdentifierDetails> => {
    const symbol = id[0].toUpperCase() + id.slice(1); // Ensure first letter upper
    const element = ELEMENTS_TABLE[symbol];

    if (!element) {
        console.warn(`Element not found: ${symbol}`);
        return {
            name: "Unknown Element",
            database_link: "TBD",
            image: "",
        };
    }

    return {
        name: element.fullName,
        database_link: `https://pubchem.ncbi.nlm.nih.gov/element/${element.atomicId}`,
        image: "", // no image
    };
};

const ShowIdentifiers: FC<Props> = ({ uuid }) => {
    const [activeSegment, setActiveSegment] = useState<string | null>(null);
    const [segmentName, setSegmentName] = useState<string | null>(null);
    const [identifiers, setIdentifiers] = useState<Identifier[]>([]);
    const [loading, setLoading] = useState(false);
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [detailsMap, setDetailsMap] = useState<Record<string, IdentifierDetails>>({});

    // Placeholder fetch functions for each identifier_type
    const fetchIdentifierDetails = async (type: string, id: string): Promise<IdentifierDetails> => {
        switch (type) {
            case "PUBCHEM_CID":
                return await fetchPubChemCIDDetails(id);
            case "CHEMBL_ID":
                return await fetchChEMBLDetails(id);
            case "CHEBI_ID":
                return await fetchChEBIDetails(id);
            case "PDB_ID":
                return await fetchPDBDetails(id);
            case "ELEMENT":
                return await fetchElementDetails(id);
            case "INCHIKEY":
            case "UNIPROT_ID":
            case "ALPHAFOLD_ID":
            default:
                return {
                    name: `${id} from ${type}`,
                    database_link: "https://www.google.com",
                    image: "", // empty string for now
                };
        }
    };

    useEffect(() => {
        if (!activeSegment) return;
        const fetchIdentifiers = async () => {
            setLoading(true);
            try {
                const res = await fetch(`/api/annotate/${uuid}/results/identifiers/${activeSegment}`);
                const data = await res.json();
                setIdentifiers(data.results || []);
            } catch (err) {
                console.error("Failed to fetch identifiers:", err);
                setIdentifiers([]);
            } finally {
                setLoading(false);
            }
        };
        fetchIdentifiers();
    }, [uuid, activeSegment]);

    const handleAccordionChange = (id: string) => async (_: any, isExpanded: boolean) => {
        setExpandedId(isExpanded ? id : null);
        if (isExpanded && !detailsMap[id]) {
            // Find type for this ID
            const ident = identifiers.find((i) => i.identifier_id === id);
            if (ident) {
                const details = await fetchIdentifierDetails(ident.identifier_type, ident.identifier_id);
                setDetailsMap((prev) => ({ ...prev, [id]: details }));
            }
        }
    };

    return (
        <Box sx={{ display: "flex", flexDirection: "column", height: "100%", width: "100%" }}>
            {/* Page header */}
            <Box sx={{ mb: 2 }}>
                <Typography variant="h4" fontWeight="bold" gutterBottom>
                    Database hits
                </Typography>
                <Divider />
            </Box>

            <Box sx={{ display: "flex", height: "100%" }}>
                {/* Left: segment selector */}
                <Box sx={{ flex: 2 }}>
                    <SegmentSelector
                        uuid={uuid}
                        onSelect={(segid, name) => {
                            setActiveSegment(segid);
                            setSegmentName(name);
                        }}
                    />
                </Box>

                {/* Right: identifier info */}
                <Box sx={{ flex: 3, p: 2, overflowY: "auto" }}>
                    {activeSegment ? (
                        <>
                            <Typography variant="h2" gutterBottom>
                                {segmentName} ({activeSegment})
                            </Typography>

                            {loading ? (
                                <Typography>Loading identifiers...</Typography>
                            ) : identifiers.length === 0 ? (
                                <Typography>No identifiers found.</Typography>
                            ) : (
                                identifiers.map((ident) => (
                                    <Accordion
                                        key={ident.identifier_id}
                                        expanded={expandedId === ident.identifier_id}
                                        onChange={handleAccordionChange(ident.identifier_id)}
                                        sx={{ mb: 1 }}
                                    >
                                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                            <Box sx={{ width: "100%" }}>
                                                <Typography variant="subtitle1" fontWeight="bold">
                                                    {ident.identifier_type}: {ident.identifier_id}
                                                </Typography>
                                                <Box sx={{ display: "flex", alignItems: "center", mt: 0.5 }}>
                                                    <Box sx={{ flex: 1, mr: 1 }}>
                                                        <LinearProgress
                                                            variant="determinate"
                                                            value={ident.similarity}
                                                            sx={{ height: 10, borderRadius: 5 }}
                                                        />
                                                    </Box>
                                                    <Typography variant="body2" minWidth={35}>
                                                        {ident.similarity.toFixed(1)}%
                                                    </Typography>
                                                </Box>
                                            </Box>
                                        </AccordionSummary>

                                        <AccordionDetails>
                                            {detailsMap[ident.identifier_id] ? (
                                                <Box sx={{ display: "flex", gap: 2 }}>
                                                    {/* Image */}
                                                    <Box sx={{ flex: 1 }}>
                                                        <img
                                                            src={detailsMap[ident.identifier_id].image}
                                                            alt={ident.identifier_id}
                                                            style={{ width: "100%", maxHeight: 300, objectFit: "contain" }}
                                                        />
                                                    </Box>

                                                    {/* Data */}
                                                    <Box sx={{ flex: 1, display: "flex", flexDirection: "column", gap: 1 }}>
                                                        <Typography>
                                                            <strong>ID:</strong> {ident.identifier_id}
                                                        </Typography>
                                                        <Typography>
                                                            <strong>Database link:</strong>{" "}
                                                            <Link
                                                                href={detailsMap[ident.identifier_id].database_link}
                                                                target="_blank"
                                                                rel="noopener"
                                                            >
                                                                {detailsMap[ident.identifier_id].database_link}
                                                            </Link>
                                                        </Typography>
                                                        <Typography>
                                                            <strong>Full name:</strong>{" "}
                                                            {detailsMap[ident.identifier_id].name}
                                                        </Typography>
                                                    </Box>
                                                </Box>
                                            ) : (
                                                <Typography>Loading details...</Typography>
                                            )}
                                        </AccordionDetails>
                                    </Accordion>
                                ))
                            )}
                        </>
                    ) : (
                        <Typography>Select a segment to see details.</Typography>
                    )}
                </Box>
            </Box>
        </Box>
    );
};

export default ShowIdentifiers;
