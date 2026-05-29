import { Box, Container } from '@mui/material';
import { Outlet } from 'react-router-dom';
import Header from './Header';
import Footer from './Footer';

const Layout = () => {

  return (
    <Box bgcolor={"#f6f8fa"} color={"text.primary"} sx={{p: 0}} justifyContent={"center"}>
      <Container maxWidth="xl" sx={{p: 0}}>
        <Box sx={{background: "#FFF", minHeight: "80vh", p: { xs: 1, sm: 1, md: 3, lg: 3, xl: 3 }}}>
          <Header />
          <Outlet />
        </Box>
        <Box>
          <Footer />
        </Box>
      </Container>
    </Box>
  );
}

export default Layout;
