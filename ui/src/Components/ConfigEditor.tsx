import React, { useState, useEffect } from "react"
import {
    Accordion,
    AccordionSummary,
    AccordionDetails,
    TextField,
    Switch,
    FormControlLabel,
    Typography,
    Stack,
} from "@mui/material"
import ExpandMoreIcon from "@mui/icons-material/ExpandMore"

interface ConfigEditorProps {
    config: Record<string, any>
    onChange: (updated: Record<string, any>) => void
}

const ConfigEditor: React.FC<ConfigEditorProps> = ({ config, onChange }) => {
    const [localConfig, setLocalConfig] = useState<Record<string, any>>({})

    useEffect(() => {
        // Initialize local state from prop, filtering out private keys
        const filtered: Record<string, any> = {}
        for (const [key, value] of Object.entries(config)) {
            if (!key.startsWith("_")) {
                filtered[key] = value
            }
        }
        setLocalConfig(filtered)
    }, [config])

    const updateValue = (section: string, field: string, value: any) => {
        const updated = {
            ...localConfig,
            [section]: {
                ...localConfig[section],
                [field]: value,
            },
        }
        setLocalConfig(updated)
        onChange(updated)
    }

    // Filter out private keys (starting with _)
    const sections = Object.entries(config).filter(([key]) => !key.startsWith("_"))

    if (sections.length === 0) {
        return <Typography variant="body2" color="text.secondary">No configuration sections available</Typography>
    }

    return (
        <Stack spacing={2}>
            {sections.map(([sectionName, sectionData]) => {
                if (typeof sectionData !== "object" || sectionData === null) {
                    return null
                }

                const fields = Object.entries(sectionData)

                return (
                    <Accordion key={sectionName} defaultExpanded>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                            <Typography variant="subtitle1" fontWeight="bold">
                                {sectionName.charAt(0).toUpperCase() + sectionName.slice(1)}
                            </Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                            <Stack spacing={2}>
                                {fields.map(([fieldName, value]) => {
                                    // Skip private fields
                                    if (fieldName.startsWith("_")) {
                                        return null
                                    }

                                    if (typeof value === "boolean") {
                                        return (
                                            <FormControlLabel
                                                key={fieldName}
                                                control={
                                                    <Switch
                                                        checked={localConfig[sectionName]?.[fieldName] ?? value}
                                                        onChange={(e) =>
                                                            updateValue(sectionName, fieldName, e.target.checked)
                                                        }
                                                    />
                                                }
                                                label={
                                                    <Typography variant="body2">
                                                        {fieldName.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                                                    </Typography>
                                                }
                                            />
                                        )
                                    } else if (typeof value === "number") {
                                        return (
                                            <TextField
                                                key={fieldName}
                                                label={fieldName.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                                                type="number"
                                                size="small"
                                                fullWidth
                                                value={localConfig[sectionName]?.[fieldName] ?? value}
                                                onChange={(e) =>
                                                    updateValue(sectionName, fieldName, parseFloat(e.target.value) || 0)
                                                }
                                            />
                                        )
                                    } else {
                                        return (
                                            <TextField
                                                key={fieldName}
                                                label={fieldName.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                                                type="text"
                                                size="small"
                                                fullWidth
                                                value={localConfig[sectionName]?.[fieldName] ?? value}
                                                onChange={(e) =>
                                                    updateValue(sectionName, fieldName, e.target.value)
                                                }
                                            />
                                        )
                                    }
                                })}
                            </Stack>
                        </AccordionDetails>
                    </Accordion>
                )
            })}
        </Stack>
    )
}

export default ConfigEditor
