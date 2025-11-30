import { Box, Typography, Paper, LinearProgress, Chip, Grid } from '@mui/material';
import { CheckCircle, Construction } from '@mui/icons-material';
import { useColonizationStore } from '../../stores/colonizationStore';
import { ConstructionSite, CommodityStatus } from '../../types/colonization';

export const SiteList = () => {
  const { systemData } = useColonizationStore();

  if (!systemData || systemData.construction_sites.length === 0) {
    return (
      <Box sx={{ textAlign: 'center', py: 4 }}>
        <Typography color="text.secondary">
          No construction sites found in this system
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* System Summary */}
      <Paper sx={{ p: 3, mb: 3, bgcolor: 'background.paper' }}>
        <Typography variant="h5" gutterBottom>
          {systemData.system_name}
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              Total Sites
            </Typography>
            <Typography variant="h6">{systemData.total_sites}</Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              Completed
            </Typography>
            <Typography variant="h6" color="success.main">
              {systemData.completed_sites}
            </Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              In Progress
            </Typography>
            <Typography variant="h6" color="warning.main">
              {systemData.in_progress_sites}
            </Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              Overall Progress
            </Typography>
            <Typography variant="h6">
              {systemData.completion_percentage.toFixed(1)}%
            </Typography>
          </Grid>
        </Grid>
      </Paper>

      {/* Construction Sites */}
      {systemData.construction_sites.map((site) => (
        <SiteCard key={site.market_id} site={site} />
      ))}
    </Box>
  );
};

const SiteCard = ({ site }: { site: ConstructionSite }) => {
  const isComplete = site.construction_complete;
  const statusColor = isComplete ? 'success.main' : 'info.main';
  const statusIcon = isComplete ? <CheckCircle /> : <Construction />;

  return (
    <Paper sx={{ p: 3, mb: 2, bgcolor: 'background.paper' }}>
      {/* Site Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
        <Box sx={{ color: statusColor }}>{statusIcon}</Box>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h6">{site.station_name}</Typography>
          <Typography variant="body2" color="text.secondary">
            {site.station_type}
          </Typography>
        </Box>
        <Chip
          label={isComplete ? 'COMPLETE' : 'IN PROGRESS'}
          color={isComplete ? 'success' : 'info'}
          size="small"
        />
        <Chip
          label={`Source: ${site.last_source || 'journal'}`}
          size="small"
          variant="outlined"
          sx={{ ml: 1 }}
        />
      </Box>

      {/* Progress Bar */}
      <Box sx={{ mb: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="body2" color="text.secondary">
            Construction Progress
          </Typography>
          <Typography variant="body2" fontWeight="bold">
            {site.construction_progress.toFixed(1)}%
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={site.construction_progress}
          sx={{
            height: 8,
            borderRadius: 1,
            bgcolor: 'grey.800',
            '& .MuiLinearProgress-bar': {
              bgcolor: isComplete ? 'success.main' : 'info.main',
            },
          }}
        />
      </Box>

      {/* Commodities */}
      {site.commodities.length > 0 && (
        <Box>
          <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>
            Commodities Required:
          </Typography>
          {site.commodities.map((commodity, index) => (
            <Box
              key={index}
              sx={{
                p: 2,
                mb: 1,
                bgcolor: 'background.default',
                borderRadius: 1,
                borderLeft: 4,
                borderColor:
                  commodity.status === CommodityStatus.COMPLETED
                    ? 'success.main'
                    : commodity.status === CommodityStatus.IN_PROGRESS
                    ? 'warning.main'
                    : 'grey.700',
              }}
            >
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography
                  variant="body1"
                  fontWeight="medium"
                  sx={{
                    color:
                      commodity.status === CommodityStatus.COMPLETED
                        ? 'success.main'
                        : commodity.status === CommodityStatus.IN_PROGRESS
                        ? 'warning.main'
                        : 'text.primary',
                  }}
                >
                  {commodity.status === CommodityStatus.COMPLETED && '✓ '}
                  {commodity.name_localised}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Payment: {commodity.payment.toLocaleString()} CR
                </Typography>
              </Box>

              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2" color="text.secondary">
                  {commodity.provided_amount.toLocaleString()} /{' '}
                  {commodity.required_amount.toLocaleString()}
                  {commodity.remaining_amount > 0 && (
                    <span style={{ color: '#FF9800', marginLeft: 8 }}>
                      (Need {commodity.remaining_amount.toLocaleString()} more)
                    </span>
                  )}
                </Typography>
                <Typography variant="body2" fontWeight="bold">
                  {commodity.progress_percentage.toFixed(1)}%
                </Typography>
              </Box>

              <LinearProgress
                variant="determinate"
                value={commodity.progress_percentage}
                sx={{
                  height: 6,
                  borderRadius: 1,
                  bgcolor: 'grey.800',
                  '& .MuiLinearProgress-bar': {
                    bgcolor:
                      commodity.status === CommodityStatus.COMPLETED
                        ? 'success.main'
                        : 'warning.main',
                  },
                }}
              />
            </Box>
          ))}
        </Box>
      )}

      {isComplete && (
        <Box sx={{ mt: 2, p: 2, bgcolor: 'success.dark', borderRadius: 1 }}>
          <Typography color="success.contrastText" textAlign="center">
            ✓ All commodities delivered - Construction complete!
          </Typography>
        </Box>
      )}
    </Paper>
  );
};