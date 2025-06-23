import { Button, Paper, Stack, Typography } from "@mui/material";
import React from "react";
import { useNavigate } from 'react-router-dom';
// import ProteinViewer from "./ProteinViewer";

interface ExampleProps {
    name: string
    description?: React.ReactElement | string
    id: string
    img: string
}

const Example = (props: ExampleProps) => {
    const { name, description, id, img } = props
    const navigate = useNavigate()

    return (
        <Paper elevation={3} sx={{ padding: 2, margin: 2, height:"100%" }}>
            <Stack spacing={2} justifyContent="center" alignItems="center" margin={2}>
                <img src={"/examples/" + img} height={250} width={250} alt="Protein structure of {name}"/>
                <Typography variant="h3" fontWeight="bold">{name}</Typography>
                {description && <Typography>{description}</Typography>}
                <Button size="large" variant="contained" color="primary" onClick={() => navigate(`/results/${id}`)}>View metadata</Button>
            </Stack>
        </Paper>
    )
}

export default Example
