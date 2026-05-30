import { FormControl, InputLabel, Select, MenuItem, Box, SelectChangeEvent, Typography } from "@mui/material";

interface SegmentMeta {
    type?: string;
    atom_count?: number;
    residue_count?: number;
}

interface SegmentSelectorProps {
    segments: string[];
    selectedSegment: string;
    onSelect: (segment: string) => void;
    segmentMeta?: Record<string, SegmentMeta>;
}

const SegmentSelector: React.FC<SegmentSelectorProps> = ({ 
    segments, 
    selectedSegment, 
    onSelect,
    segmentMeta,
}) => {
    const handleChange = (event: SelectChangeEvent<string>) => {
        onSelect(event.target.value);
    };

    const getSegmentLabel = (segment: string): string => {
        const meta = segmentMeta?.[segment];
        if (meta?.type) {
            return `${segment} (${meta.type})`;
        }
        return segment;
    };

    return (
        <Box sx={{ display: "flex", height: "100%", p: 2 }}>
            <FormControl fullWidth size="small">
                <InputLabel id="segment-selector-label">Molecule</InputLabel>
                <Select
                    labelId="segment-selector-label"
                    value={selectedSegment}
                    label="Molecule"
                    onChange={handleChange}
                    disabled={segments.length === 0}
                    sx={{
                        "& .MuiSelect-select": {
                            fontSize: "1rem",
                        },
                    }}
                >
                    <MenuItem value="SYSTEM" sx={{ fontWeight: "bold" }}>
                        Whole System
                    </MenuItem>
                    {segments.map((segment) => (
                        <MenuItem key={segment} value={segment}>
                            {getSegmentLabel(segment)}
                        </MenuItem>
                    ))}
                </Select>
            </FormControl>
            {segments.length === 0 && (
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
                    No molecule segments detected.
                </Typography>
            )}
        </Box>
    );
};

export default SegmentSelector;
