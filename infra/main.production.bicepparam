using 'main.bicep'

param env = 'production'
param appLocation = 'spaincentral'
param maxReplicas = 5
param retentionDays = 730
param dailyCapGb = '0.5'
param budgetAmount = 20
param digest = readEnvironmentVariable('IMAGE_DIGEST')
param revisionSuffix = readEnvironmentVariable('REVISION_SUFFIX')
param stableRevision = readEnvironmentVariable('STABLE_REVISION', '')
param authClientId = readEnvironmentVariable('AUTH_CLIENT_ID')
param foundryProjectEndpoint = readEnvironmentVariable('FOUNDRY_PROJECT_ENDPOINT')
param docintelEndpoint = readEnvironmentVariable('DOCINTEL_ENDPOINT')
param alertEmail = readEnvironmentVariable('ALERT_EMAIL_ADDRESS')
