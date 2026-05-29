import { ArrowDropDown, DataObject, Article } from "@mui/icons-material";
import { Button, Menu, MenuItem, Checkbox, FormControlLabel, Box, ButtonGroup, Typography, Icon, Stack, Divider } from "@mui/material";
import { useState } from "react";
import { stringify } from "yaml";
import { IconLabel, iconMap } from "./FormsWrapper";
import { AnnotationResultsStatusResponse } from "../Pages/AnnotationResults";

interface DownloadMetadataActionsProps {
    uuid: string;
    what: "results" | "log";
}

const DownloadMetadataActions = ({ uuid, what }: DownloadMetadataActionsProps): React.ReactElement => {
    const downloadUrl = `/api/annotate/${uuid}/${what}`;
    const fileExtension = what === "log" ? "log.txt" : "results.json";

    const handleDownload = async () => {
        try {
            const response = await fetch(downloadUrl);
            if (!response.ok) throw new Error("Failed to download file");

            const blob = await response.blob();
            const element = document.createElement("a");
            element.href = URL.createObjectURL(blob);
            element.download = `${uuid}-${new Date().toISOString()}.${fileExtension}`;
            document.body.appendChild(element);
            element.click();
            element.remove();
        } catch (error) {
            console.error(`[Download ${what}]`, error);
        }
    };

    return (
        <ButtonGroup
            variant="contained"
            color="primary"
            size="large"
            aria-label={`Download ${what}`}
        >
            <Button
                onClick={handleDownload}
                endIcon={what === "log" ? <Article /> : <DataObject />}
            >
                Download {what === "log" ? "Log" : "Results"}
            </Button>
        </ButtonGroup>
    );
};

export default DownloadMetadataActions;