import { FC, useEffect, useState } from "react";
import { Box, Typography, Table, TableBody, TableCell, TableRow, Divider } from "@mui/material";
import SegmentSelector from "../MDComponents/SegmentSelector";

interface Props {
    uuid: string;
}

interface FlagsResponse {
    [flag: string]: {
        value: boolean;
        description: string;
    };
}

const ShowLoad: FC<Props> = ({ uuid }) => {
    const [activeSegment, setActiveSegment] = useState<string | null>(null);
    const [segmentName, setSegmentName] = useState<string | null>(null);

    const [atoms, setAtoms] = useState<number | null>(null);
    const [bonds, setBonds] = useState<number | null>(null);
    const [molecules, setMolecules] = useState<number | null>(null);
    const [atomsInMolecule, setAtomsInMolecule] = useState<number | null>(null);
    const [bondsInMolecule, setBondsInMolecule] = useState<number | null>(null);
    const [flags, setFlags] = useState<FlagsResponse>({});

    useEffect(() => {
        if (!activeSegment) return;

        const fetchData = async () => {
            const endpoints: [string, (val: any) => void][] = [
                ["atoms", (d) => setAtoms(d.result)],
                ["bonds", (d) => setBonds(d.result)],
                ["molecules", (d) => setMolecules(d.result)],
                ["atoms_in_molecule", (d) => setAtomsInMolecule(d.result)],
                ["bonds_in_molecule", (d) => setBondsInMolecule(d.result)],
                ["flags", (d) => setFlags(d.result)],
            ];

            for (const [what, setter] of endpoints) {
                try {
                    const res = await fetch(`/api/annotate/${uuid}/results/segmentinfo/${activeSegment}/${what}`);
                    const data = await res.json();
                    setter(data);
                } catch (err) {
                    console.error(`Failed to fetch ${what}:`, err);
                }
            }
        };

        fetchData();
    }, [uuid, activeSegment]);

    return (
        <Box sx={{ display: "flex", flexDirection: "column", height: "100%", width: "100%" }}>
            {/* Page header */}
            <Box sx={{ mb: 2 }}>
                <Typography variant="h4" fontWeight="bold" gutterBottom>
                    Simulation load information
                </Typography>
                <Divider />
            </Box>
        <Box sx={{ display: "flex", height: "100%" }}>
            {/* Left: segment selector */}
            <Box sx={{ flex: 1 }}>
                <SegmentSelector
                    uuid={uuid}
                    onSelect={(segid, name) => {
                        setActiveSegment(segid);
                        setSegmentName(name);
                    }}
                />
            </Box>

            {/* Right: segment info */}
            <Box sx={{ flex: 2, p: 2, overflowY: "auto" }}>
                {activeSegment ? (
                    <>
                        {/* Segment name */}
                        <Typography variant="h2" gutterBottom>
                            {segmentName} ({activeSegment})
                        </Typography>

                        {/* Stats */}
                        <Typography variant="subtitle1">Molecules in segment: {molecules ?? "–"}</Typography>
                        <Typography variant="subtitle1">Atoms in molecule: {atomsInMolecule ?? "–"}</Typography>
                        <Typography variant="subtitle1">Bonds in molecule: {bondsInMolecule ?? "–"}</Typography>
                        <Typography variant="subtitle1">Total atoms: {atoms ?? "–"}</Typography>
                        <Typography variant="subtitle1">Total bonds: {bonds ?? "–"}</Typography>

                        {/* Flags table */}
                        <Box sx={{ mt: 3 }}>
                            <Typography variant="h5" gutterBottom>
                                Flags
                            </Typography>
                            <Table size="small" sx={{ border: "none" }}>
                                <TableBody>
                                    {Object.entries(flags).map(([flag, info]) => (
                                        <TableRow key={flag} sx={{ borderBottom: "none" }}>
                                            <TableCell sx={{ border: "none", width: "20%", fontWeight: "bold" }}>
                                                {flag}
                                            </TableCell>
                                            <TableCell sx={{ border: "none", width: "20%" }}>
                                                <Typography
                                                    sx={{
                                                        fontWeight: "bold",
                                                        color: info.value ? "green" : "gray",
                                                        fontSize: "1.1rem",
                                                    }}
                                                >
                                                    {info.value ? "Available" : "Unavailable"}
                                                </Typography>
                                            </TableCell>
                                            <TableCell sx={{ border: "none" }}>{info.description}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </Box>
                    </>
                ) : (
                    <Typography>Select a segment to see details.</Typography>
                )}
            </Box>
        </Box>
        </Box>
    );
};

export default ShowLoad;
