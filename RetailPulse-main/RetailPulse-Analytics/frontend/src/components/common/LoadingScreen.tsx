import { Box, CircularProgress, Typography } from "@mui/material";

export function LoadingScreen({ label = "Loading RetailPulse..." }: { label?: string }) {
  return (
    <Box
      minHeight="100vh"
      display="flex"
      alignItems="center"
      justifyContent="center"
      flexDirection="column"
      gap={2}
    >
      <CircularProgress />
      <Typography variant="body1" color="text.secondary">
        {label}
      </Typography>
    </Box>
  );
}
