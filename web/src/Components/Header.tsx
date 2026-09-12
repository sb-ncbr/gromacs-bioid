import { GitHub, Mail, Help, AccountCircle, BugReport, Assessment } from "@mui/icons-material";
import { Box, Link, Divider, IconButton, Stack, Tooltip, Typography, Chip } from "@mui/material"
import { useNavigate } from "react-router-dom";

const Header = () => {

    const navigate = useNavigate();

    return (
        <Box sx={{mt: 3, mb: 3}}>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Stack direction={'column'} spacing={1} sx={{flexGrow: 1}}>
                    <Stack direction="row" alignItems="center" onClick={() => navigate("/")} sx={{color: "inherit", cursor: "pointer"}}>
                        <Typography variant="h1">Molecular Dynamics <span style={{color: "rgb(46, 125, 50)"}}>Bio</span>ID</Typography>
                        <Chip 
                            label="Validation" 
                            size="small" 
                            sx={{ml: 2, bgcolor: "rgba(46, 125, 50, 0.1)", color: "rgb(46, 125, 50)", fontWeight: "bold"}}
                        />
                    </Stack>
                    <Typography variant="h3" sx={{mt: "0.5em"}}>Yet another tool to describe molecular dynamics simulations with powerful metadata</Typography>
                </Stack>
                <Box>
                    {/* Failure Analysis Link */}
                    <Tooltip title="Analyze validation failures">
                        <IconButton 
                            onClick={() => navigate("/failure-analysis")} 
                            size="small"
                            sx={{mr: 1}}
                        >
                            <Assessment sx={{fontSize: "2em", color: "rgb(46, 125, 50)"}}/>
                        </IconButton>
                    </Tooltip>
                    
                    <Tooltip title="Github">
                        <IconButton href="https://github.com/cerit-muni/bat3" size="small" target="_blank">
                            <GitHub sx={{fontSize: "2em", color: "rgb(46, 125, 50)"}}/>
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Contact us">
                        <IconButton href="mailto:tomas.pavlik@muni.cz" size="small" target="_blank">
                            <Mail sx={{fontSize: "2em"}}/>
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Manual">
                        <IconButton href="https://github.com/cerit-muni/bat3#readme" size="small" target="_blank">
                            <Help sx={{fontSize: "2em"}}/>
                        </IconButton>
                    </Tooltip>
                </Box>
            </Stack>
            <Divider sx={{mt: "1em"}}/>
        </Box>
    )
}

export default Header;
