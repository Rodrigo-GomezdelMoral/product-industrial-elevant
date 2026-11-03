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
@description('Region of the shared Container Apps environment and both apps: spaincentral, where preflight allows it; data, identities and monitoring stay in location (ADR-017).')
param appLocation string = location
param registryName string = 'craiplatformshared'

var short = env == 'staging' ? 'stg' : 'prod'
var tags = { project: 'product-industrial-elevant', environment: env, owner: 'Rodrigo-GomezdelMoral' }
var registryServer = '${registryName}${environment().suffixes.acrLoginServer}'
var environmentName = 'cae-elevant-env'
var environmentGroup = 'rg-elevant-prod-swc'

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

@description('Only production declares the shared Container Apps environment; staging joins it as existing (ADR-016).')
module containerEnvironment 'modules/environment.bicep' = if (env == 'production') {
  params: { name: environmentName, location: appLocation, tags: union(tags, { environment: 'shared' }), workspaceId: monitoring.outputs.workspaceId }
}

resource sharedEnvironment 'Microsoft.App/managedEnvironments@2026-07-01' existing = { name: environmentName, scope: resourceGroup(environmentGroup) }

module app 'modules/app.bicep' = {
  dependsOn: [containerEnvironment]
  params: {
    location: appLocation, environmentId: sharedEnvironment.id, tags: tags, short: short, production: env == 'production', maxReplicas: maxReplicas
    image: '${registryServer}/product-industrial-elevant@${digest}', registryServer: registryServer, identityId: identity.id
    revisionSuffix: revisionSuffix, stableRevision: stableRevision, authClientId: authClientId
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
