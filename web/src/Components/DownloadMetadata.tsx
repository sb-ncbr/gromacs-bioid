import { ArrowDropDown, DataObject } from "@mui/icons-material";
import { Button, Menu, MenuItem, Checkbox, FormControlLabel, Box, ButtonGroup, Typography, Icon, Stack, Divider } from "@mui/material";
import { useState } from "react";
import { stringify } from "yaml";
import { IconLabel, iconMap } from "./FormsWrapper";
import { AnnotationResultsStatusResponse } from "../Pages/AnnotationResults";

interface DownloadMetadataActionsProps {
    data: Object;
    stateData: AnnotationResultsStatusResponse;
    mode?: "basic" | "advanced";
}

const DownloadMetadataActions = ({ data, stateData, mode = "basic" }: DownloadMetadataActionsProps): React.ReactElement => {
    const [anchorElem, setAnchorElem] = useState<null | HTMLElement>(null);
    const [selectedKeys, setSelectedKeys] = useState<string[]>(Object.keys(data));

    const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
        setAnchorElem(event.currentTarget);
    };

    const handleCheckboxChange = (key: string) => {
        setSelectedKeys((prev) =>
            prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
        );
    };

    // Select all keys
    const handleSelectAll = () => {
        setSelectedKeys(Object.keys(data));
    };

    // Deselect all keys
    const handleSelectNone = () => {
        setSelectedKeys([]);
    };

    const downloadMetadata = (format: string): void => {
        const fileName = stateData.processed_files.tpr?.split(".").slice(0, -1).join(".");
        const element = document.createElement("a");

        // Filter data.result based on selected keys (if in advanced mode)
        const filteredData = mode === "advanced" && selectedKeys.length > 0
            ? Object.fromEntries(selectedKeys.map((key) => [key, (data as { [key: string]: any })[key]]))
            : data;

        let file = new Blob();
        if (format === "yaml") {
            file = new Blob([stringify(filteredData)], { type: 'text/plain' });
        } else if (format === "json") {
            file = new Blob([JSON.stringify(filteredData, null, 2)], { type: 'text/plain' });
        }

        element.href = URL.createObjectURL(file);
        element.download = `${fileName || "unknown"}-${new Date().toISOString()}.metadata.${format}`;
        document.body.appendChild(element);
        element.click();
        handleClose();
    };

    const handleClose = () => {
        setAnchorElem(null);
    };

    return (
        <>
            {mode === "advanced" && (
                <Box sx={{ p: 2 }}>
                    {/* All/None Checkboxes */}
                    <Box sx={{ display: "flex", gap: 2, mb: 2 }}>
                        
                    </Box>

                    <Stack direction="column" spacing={1}>
                        <Stack direction="row" spacing={1} alignItems={"center"}>
                            <Typography variant="h3">Select Metadata Fields</Typography>
                            <ButtonGroup variant="outlined" color="primary" size="small">
                                <Button onClick={handleSelectAll}>Select All</Button>
                                <Button onClick={handleSelectNone}>Select None</Button>
                            </ButtonGroup>
                        </Stack>
                    {Object.keys(data).map((key) => (
                        <FormControlLabel
                            key={key}
                            control={
                                <Checkbox
                                    checked={selectedKeys.includes(key)}
                                    onChange={() => handleCheckboxChange(key)}
                                />
                            }
                            label={<IconLabel label={key} />}
                        />
                    ))}
                    </Stack>
                </Box>
            )}
            <ButtonGroup
                variant="contained"
                color="primary"
                size="large"
                aria-label="contained primary button group"
            >
                <Button endIcon={<DataObject />} onClick={() => downloadMetadata("json")}>Download Metadata</Button>
            </ButtonGroup>

        </>
    );
};

export default DownloadMetadataActions;