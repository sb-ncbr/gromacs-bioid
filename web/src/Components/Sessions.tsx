import { RemoveCircle, Visibility } from "@mui/icons-material";
import { Table, TableHead, TableRow, TableCell, TableBody, IconButton, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

export interface AnnotationSessionRecord {
    id: string;
    title: string;
    uploadedFiles: string[];
    date: string;

}
const Sessions = () => {
    
    const navigate = useNavigate();

    const [requestIds, setRequestIds] = useState<AnnotationSessionRecord[]>([]);
    
    useEffect(() => {
        const storedRequestIds = localStorage.getItem("request_ids");
        if (storedRequestIds) {
            setRequestIds(JSON.parse(storedRequestIds));
        }
    }, []);

    const handleRemoveSession = (requestId: string): void => {
        const updatedRequestIds = requestIds.filter(record => record.id !== requestId);
        setRequestIds(updatedRequestIds);
        localStorage.setItem("request_ids", JSON.stringify(updatedRequestIds));
    }

    if (requestIds.length > 0){
        return (
            <>
                <Typography variant="h1" sx={{mb: 0}}>Previous sessions</Typography>
                <Table sx={{ width: {xs: "100%", sm: "100%", md: "100%", lg: "70%", xl: "50%"}, mt: 0 }} size="small">
                    <TableHead>
                        <TableRow>
                            <TableCell>Title</TableCell>
                            <TableCell>Date</TableCell>
                            <TableCell></TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {requestIds.map((record, index) => (
                            <TableRow key={index}>
                                <TableCell>{record.title}</TableCell>
                                <TableCell>{(new Date(record.date)).toLocaleString()}</TableCell>
                                <TableCell>
                                    <IconButton onClick={() => navigate(`/results/${record.id}`)}>
                                        <Visibility />
                                    </IconButton>
                                    <IconButton onClick={() => handleRemoveSession(record.id)}>
                                        <RemoveCircle />
                                    </IconButton>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </>
        );

    } else {
        // return (
        //     <>
        //         <Typography variant="h1" sx={{mb: 0}}>Sessions</Typography>
        //         <Typography>No recent sessions available. Start a new one by annotating simulation files.</Typography>
        //     </>
        // );
    }
}

export default Sessions;