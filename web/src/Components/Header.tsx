import { GitHub, Mail, Help, AccountCircle } from "@mui/icons-material";
import { Box, Link, Divider, IconButton, Stack, Tooltip, Typography } from "@mui/material"
import { useNavigate } from "react-router-dom";

const Header = () => {

    const navigate = useNavigate();

    return (
        <Box sx={{mt: 3, mb: 3}}>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Stack direction={'column'} spacing={1} sx={{flexGrow: 1}}>
                    <Stack direction="row" alignItems="center" onClick={() => navigate("/")} sx={{color: "inherit", cursor: "pointer"}}>
                        <Typography variant="h1">GROMACS <span style={{color: "rgb(46, 125, 50)"}}>Bio</span>ID</Typography>
                    </Stack>
                    <Typography variant="h3" sx={{mt: "0.5em"}}>Yet another tool to describe molecular dynamics simulations with powerful metadata</Typography>
                </Stack>
                <Box>
                    { /* TODO: add actual links */}
                    <Tooltip title="Github">
                        <IconButton href="https://www.google.com" size="small" target="_blank">
                            <GitHub sx={{fontSize: "2em", color: "rgb(46, 125, 50)"}}/>
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Contact us">
                        <IconButton href="mailto:tomas.pavlik@muni.cz" size="small" target="_blank">
                            <Mail sx={{fontSize: "2em"}}/>
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Manual">
                        <IconButton href="www.google.com" size="small" target="_blank">
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