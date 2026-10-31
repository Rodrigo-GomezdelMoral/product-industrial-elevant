using 'main.bicep'

param env = 'staging'
param maxReplicas = 3
param retentionDays = 30
param dailyCapGb = '0.1'
param budgetAmount = 5
param digest = readEnvironmentVariable('IMAGE_DIGEST')
param revisionSuffix = readEnvironmentVariable('REVISION_SUFFIX')
param authClientId = readEnvironmentVariable('AUTH_CLIENT_ID')
param operatorPrincipalId = readEnvironmentVariable('OPERATOR_PRINCIPAL_ID')
param foundryProjectEndpoint = readEnvironmentVariable('FOUNDRY_PROJECT_ENDPOINT')
param docintelEndpoint = readEnvironmentVariable('DOCINTEL_ENDPOINT')
param alertEmail = readEnvironmentVariable('ALERT_EMAIL_ADDRESS')
