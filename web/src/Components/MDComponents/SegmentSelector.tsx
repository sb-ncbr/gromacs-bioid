import { useEffect, useState } from "react";
import { Box, Tabs, Tab, Typography } from "@mui/material";

interface SegmentSelectorProps {
    uuid: string;
    onSelect: (segmentId: string, segmentName: string) => void;
}

const SegmentSelector: React.FC<SegmentSelectorProps> = ({ uuid, onSelect }) => {
    const [segments, setSegments] = useState<string[]>([]);
    const [names, setNames] = useState<string[]>([]);
    const [selectedIndex, setSelectedIndex] = useState(0);

    useEffect(() => {
        const fetchSegments = async () => {
            try {
                const res = await fetch(`/api/annotate/${uuid}/results/segments`);
                const data = await res.json();
                setSegments(data.segments);
                setNames(data.names);

                // set default, but do NOT fire onSelect immediately
                if (data.segments.length > 0) {
                    setSelectedIndex(0);
                }
            } catch (err) {
                console.error("Failed to fetch segments:", err);
            }
        };
        fetchSegments();
    }, [uuid]);

    // when selectedIndex changes, notify parent
    useEffect(() => {
        if (segments.length > 0 && names.length > 0) {
            onSelect(segments[selectedIndex], names[selectedIndex]);
        }
    }, [selectedIndex, segments, names, onSelect]);

    const handleChange = (event: React.SyntheticEvent, newIndex: number) => {
        setSelectedIndex(newIndex);
        onSelect(segments[newIndex], names[newIndex]);
    };

    return (
        <Box sx={{ display: "flex", height: "100%" }}>
            <Tabs
                orientation="vertical"
                value={selectedIndex}
                onChange={handleChange}
                sx={{
                    borderRight: 1,
                    borderColor: "divider",
                    minWidth: 200,
                    "& .MuiTab-root": {
                        fontSize: "1.2rem",
                        textTransform: "none",
                        alignItems: "flex-start",
                    },
                }}
            >
                {names.map((name, idx) => (
                    <Tab
                        key={segments[idx]}
                        label={
                            <Typography variant="h5" sx={{ fontWeight: selectedIndex === idx ? "bold" : "normal" }}>
                                {name}
                            </Typography>
                        }
                    />
                ))}
            </Tabs>
        </Box>
    );
};

export default SegmentSelector;
