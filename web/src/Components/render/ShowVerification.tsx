// ShowVerification.tsx
import { FC, useEffect, useState } from "react";
import {
    Box,
    Typography,
    Divider,
    LinearProgress,
    CircularProgress,
    Link,
} from "@mui/material";

import SegmentSelector from "../MDComponents/SegmentSelector";
import MDViewer from "../MDComponents/MDViewer"; // assumed to exist

interface Props {
    uuid: string;
}

interface VerificationData {
    ident: string;
    ident_type: string;
    confidence: number;
    simulation: string; // path or data, depending on MDViewer
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

const ShowVerification: FC<Props> = ({ uuid }) => {
    const [activeSegment, setActiveSegment] = useState<string | null>(null);
    const [segmentName, setSegmentName] = useState<string | null>(null);
    const [segments, setSegments] = useState<string[]>([]);
    const [loading, setLoading] = useState(false);
    const [verification, setVerification] = useState<VerificationData | null>(null);
    const [identifierDetails, setIdentifierDetails] = useState<any | null>(null);

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
        const fetchVerification = async () => {
            setLoading(true);
            try {
                const [simulationRes, identRes, typeRes, confRes] = await Promise.all([
                    fetch(`/api/annotate/${uuid}/results/verification/${activeSegment}/simulation`),
                    fetch(`/api/annotate/${uuid}/results/verification/${activeSegment}/ident`),
                    fetch(`/api/annotate/${uuid}/results/verification/${activeSegment}/ident_type`),
                    fetch(`/api/annotate/${uuid}/results/verification/${activeSegment}/confidence`),
                ]);

                const res = await fetch(`/api/annotate/${uuid}/results/segments`);
                const data = await res.json();
                setSegments(data.segments);

                const simulationJson = await simulationRes.json();
                const identJson = await identRes.json();
                const typeJson = await typeRes.json();
                const confJson = await confRes.json();

                const verificationData: VerificationData = {
                    simulation: simulationJson.result,
                    ident: identJson.result,
                    ident_type: typeJson.result,
                    confidence: confJson.result,
                };

                setVerification(verificationData);

                // Fetch identifier details for the molecule
                const details = await fetchIdentifierDetails(
                    verificationData.ident_type,
                    verificationData.ident
                );
                setIdentifierDetails(details);
            } catch (err) {
                console.error("Failed to fetch verification:", err);
                setVerification(null);
                setIdentifierDetails(null);
            } finally {
                setLoading(false);
            }
        };
        fetchVerification();
    }, [uuid, activeSegment]);

    return (
        <Box sx={{ display: "flex", flexDirection: "column", height: "100%", width: "100%" }}>
            {/* Page header */}
            <Box sx={{ mb: 2 }}>
                <Typography variant="h4" fontWeight="bold" gutterBottom>
                    Verification results
                </Typography>
                <Divider />
            </Box>

            <Box sx={{ display: "flex", height: "100%" }}>
                {/* Left: segment selector */}
                <Box sx={{ flex: 1, pr: 2 }}>
                    <SegmentSelector
                        uuid={uuid}
                        onSelect={(segid, name) => {
                            setActiveSegment(segid);
                            setSegmentName(name);
                        }}
                    />
                </Box>

                {/* Right: verification content */}
                <Box sx={{ flex: 3, p: 2, overflowY: "auto" }}>
                    {activeSegment ? (
                        <>
                            <Typography variant="h2" gutterBottom>
                                {segmentName} ({activeSegment})
                            </Typography>

                            {loading ? (
                                <CircularProgress />
                            ) : verification && identifierDetails ? (
                                <Box sx={{ display: "flex", gap: 4 }}>
                                    {/* Left: MD Simulation */}
                                    <Box sx={{ flex: 1, borderRight: "1px solid #ddd", pr: 2 }}>
                                        <Typography variant="h5" gutterBottom>
                                            Simulation
                                        </Typography>
                                        <MDViewer
                                            session={uuid}
                                            segment={activeSegment}
                                            segments={segments}
                                            width={500}
                                            height={400}
                                        />
                                    </Box>

                                    {/* Right: Identified Molecule */}
                                    <Box sx={{ flex: 1 }}>
                                        <Typography variant="h5" fontWeight="bold" gutterBottom>
                                            {identifierDetails.name}
                                        </Typography>
                                        <Link
                                            href={identifierDetails.database_link}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            sx={{ fontSize: "1.1rem" }}
                                        >
                                            {identifierDetails.database_link}
                                        </Link>

                                        {/* Confidence bar */}
                                        <Box sx={{ mt: 3 }}>
                                            <Typography variant="body1" gutterBottom>
                                                Confidence ({verification.confidence.toFixed(2)}%)
                                            </Typography>
                                            <LinearProgress
                                                variant="determinate"
                                                value={verification.confidence}
                                                sx={{
                                                    height: 12,
                                                    borderRadius: 6,
                                                    backgroundColor: "#eee",
                                                    "& .MuiLinearProgress-bar": {
                                                        backgroundColor:
                                                            verification.confidence > 80
                                                                ? "#4caf50"
                                                                : verification.confidence > 50
                                                                    ? "#ffb300"
                                                                    : "#f44336",
                                                    },
                                                }}
                                            />
                                        </Box>

                                        {/* Molecule image */}
                                        {identifierDetails.image && (
                                            <Box
                                                component="img"
                                                src={identifierDetails.image}
                                                alt={identifierDetails.name}
                                                sx={{
                                                    mt: 3,
                                                    width: "100%",
                                                    maxHeight: 300,
                                                    objectFit: "contain",
                                                    borderRadius: 2,
                                                    boxShadow: 2,
                                                }}
                                            />
                                        )}
                                    </Box>
                                </Box>
                            ) : (
                                <Typography color="text.secondary">
                                    No verification data available for this segment.
                                </Typography>
                            )}
                        </>
                    ) : (
                        <Typography color="text.secondary">Select a segment to see verification.</Typography>
                    )}
                </Box>
            </Box>
        </Box>
    );
};

export default ShowVerification;
