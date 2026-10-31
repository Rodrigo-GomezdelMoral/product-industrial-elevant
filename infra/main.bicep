targetScope = 'resourceGroup'

@allowed(['staging', 'production'])
param env string
@description('Digest (sha256:...) of the image in the shared registry: built once per merge, promoted by digest, never rebuilt.')
param digest string
@description('Suffix of the revision this deployment creates, unique per run.')
param revisionSuffix string
@description('Production only: the revision serving traffic before this release, labelled blue; empty on the first release.')
param stableRevision string = ''
@description('Client id of the elevant-web-<env> app registration that signs users in.')
param authClientId string
@description('Staging only: object id of the operator, who exports recorded runs; empty in production, which has no human data access.')
param operatorPrincipalId string = ''
param foundryProjectEndpoint string
param docintelEndpoint string
@secure()
@description('Address that receives the budget notifications and the SLO alert.')
param alertEmail string
@minValue(1)
@maxValue(5)
param maxReplicas int
@description('Days a quote, its checkpoints and its documents are kept (REQ-10).')
param retentionDays int
@description('Daily ingestion cap of the workspace in GB, as text because Bicep has no decimal literal.')
param dailyCapGb string
@description('Monthly budget of the resource group, in the billing currency (EUR).')
param budgetAmount int
param location string = resourceGroup().location
param registryName string = 'craiplatformshared'

var short = env == 'staging' ? 'stg' : 'prod'
var tags = { project: 'product-industrial-elevant', environment: env, owner: 'Rodrigo-GomezdelMoral' }
var registryServer = '${registryName}${environment().suffixes.acrLoginServer}'

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' existing = { name: 'id-elevant-${short}' }

module monitoring 'modules/monitoring.bicep' = {
  params: {
    location: location, tags: tags, short: short, production: env == 'production', dailyCapGb: dailyCapGb
    principalId: identity.properties.principalId, alertEmail: alertEmail
  }
}

module data 'modules/data.bicep' = {
  params: {
    location: location, tags: tags, short: short, retentionDays: retentionDays, principalId: identity.properties.principalId
    operatorPrincipalId: operatorPrincipalId
  }
}

module app 'modules/app.bicep' = {
  params: {
    location: location, tags: tags, short: short, production: env == 'production', maxReplicas: maxReplicas
    image: '${registryServer}/product-industrial-elevant@${digest}', registryServer: registryServer, identityId: identity.id
    revisionSuffix: revisionSuffix, stableRevision: stableRevision, authClientId: authClientId, workspaceId: monitoring.outputs.workspaceId
    settings: {
      ELEVANT_ENV: env
      ELEVANT_IMAGE: digest
      ELEVANT_COSMOS_ENDPOINT: data.outputs.cosmosEndpoint
      ELEVANT_BLOB_ENDPOINT: data.outputs.blobEndpoint
      FOUNDRY_PROJECT_ENDPOINT: foundryProjectEndpoint
      DOCINTEL_ENDPOINT: docintelEndpoint
      AZURE_CLIENT_ID: identity.properties.clientId
      APPLICATIONINSIGHTS_CONNECTION_STRING: monitoring.outputs.connectionString
      OTEL_PYTHON_FASTAPI_EXCLUDED_URLS: 'healthz'
    }
  }
}

module budget 'modules/budget.bicep' = {
  params: { short: short, amount: budgetAmount, alertEmail: alertEmail }
}

output app string = app.outputs.name
output revision string = app.outputs.revision
