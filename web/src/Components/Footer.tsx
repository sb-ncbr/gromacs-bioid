import { Box, Divider, Stack, Typography, Link, Grid } from "@mui/material"
import logo from "../assets/elixirlogo.png"

const Footer = () => {

    return (
        <Box sx={{ mt: 5, mb: 3, bgcolor: "#f6f8fa", color: "#767676", p:3}}>
            {/* <Divider sx={{ mt: 2, mb: 2 }} /> */}
            <Grid container justifyContent="center">
                <Grid item xs={12} sm={12} md={3} lg={2} xl={2}>
                    <Box sx={{p: 5}}>
                        <img src={logo} alt="ELIXIR Czech Republic Node" />
                    </Box>
                </Grid>
                <Grid item xs={12} sm={12} md={9} lg={10} xl={10}>
                    <Box>
                        <Link href="/" variant="body1" underline="none" sx={{mb: 1, fontWeight: "bold", color: "inherit", display: "inline"}}>GROMACS <span style={{color: "rgb(46, 125, 50)"}}>Bio</span>ID</Link>
                        <Typography variant="body2" sx={{display: "inline", fontWeight: "bold"}}>
                        &nbsp; tool is a part of services provided by ELIXIR – European research infrastructure for biological information.
                        For other services provided by ELIXIR's Czech Republic Node visit <Link href="https://www.elixir-czech.cz/services">elixir-czech.cz/services</Link>.
                        </Typography>
                        <Divider sx={{ mt: 1, mb: 1 }} />
                        <Typography variant="body2" sx={{color: "#767676"}}>
                            Licence conditions in accordance with § 11 of Act No. 130/2002 Coll. The owner of the software is Masaryk University, a public university, ID: 00216224. Masaryk University allows other companies and individuals to use this software free of charge and without territorial restrictions in usual way, that does not depreciate its value. This permission is granted for the duration of property rights. This software is not subject to special information treatment according to Act No. 412/2005 Coll., as amended. In case that a person who will use the software under this licence offer violates the licence terms, the permission to use the software terminates. 
                        </Typography>
                        <Typography variant="body2" sx={{color: "#767676"}}>
                            This work was supported by the ELIXIR CZ research infrastructure project (MEYS Grant No: LM2018131), and FR CESNET grant 759/2024.
                        </Typography>
                        <Divider sx={{ mt: 1, mb: 1 }} />
                        <Typography variant="body2">&copy; {new Date().getFullYear().toString()} Made with ❤️ by <Link href="https://sb.ncbr.muni.cz/en">Structural Bioinformatics research group at Masaryk University</Link></Typography>
                    </Box>
                </Grid>
            </Grid>
        </Box>
    )
}

export default Footer;
