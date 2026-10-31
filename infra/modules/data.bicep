import { roles, roleId, uuid } from 'roles.bicep'

param location string
param tags object
param short string
param retentionDays int
@description('Principal id of the app identity, id-elevant-<env>.')
param principalId string
param operatorPrincipalId string

var app = [{ id: principalId, type: 'ServicePrincipal' }]
var grants = empty(operatorPrincipalId) ? app : concat(app, [{ id: operatorPrincipalId, type: 'User' }])
var partitions = { quotes: '/id', checkpoints: '/workflow_name' }

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2026-03-15' = {
  name: 'cosmos-elevant-${short}-swc'
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard', capabilities: [{ name: 'EnableServerless' }], consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    locations: [{ locationName: location, failoverPriority: 0, isZoneRedundant: false }]
    backupPolicy: { type: 'Continuous', continuousModeProperties: { tier: 'Continuous7Days' } }
    disableLocalAuth: true, disableKeyBasedMetadataWriteAccess: true, minimalTlsVersion: 'Tls12'
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2026-03-15' = {
  parent: cosmos
  name: 'elevant'
  properties: { resource: { id: 'elevant' } }
}

resource containers 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2026-03-15' = [
  for item in items(partitions): {
    parent: database
    name: item.key
    properties: { resource: { id: item.key, partitionKey: { paths: [item.value], kind: 'Hash' }, defaultTtl: retentionDays * 86400 } }
  }
]

resource cosmosAccess 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2026-03-15' = [
  for grant in grants: {
    parent: cosmos
    name: guid(cosmos.id, grant.id, roles.cosmosDataContributor)
    properties: {
      roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/${uuid(roles.cosmosDataContributor)}', principalId: grant.id, scope: '${cosmos.id}/dbs/${database.name}'
    }
  }
]

resource storage 'Microsoft.Storage/storageAccounts@2026-06-01' = {
  name: 'stelevant${short}swc'
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    accessTier: 'Hot', allowBlobPublicAccess: false, allowSharedKeyAccess: false, defaultToOAuthAuthentication: true
    minimumTlsVersion: 'TLS1_2', supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2026-06-01' = {
  parent: storage
  name: 'default'
  properties: { deleteRetentionPolicy: { enabled: true, days: 7 }, containerDeleteRetentionPolicy: { enabled: true, days: 7 } }
}

resource blobContainers 'Microsoft.Storage/storageAccounts/blobServices/containers@2026-06-01' = [
  for name in ['reports', 'quotes']: { parent: blobService, name: name, properties: { publicAccess: 'None' } }
]

resource lifecycle 'Microsoft.Storage/storageAccounts/managementPolicies@2026-06-01' = {
  parent: storage
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          name: 'retention', enabled: true, type: 'Lifecycle'
          definition: { filters: { blobTypes: ['blockBlob'] }, actions: { baseBlob: { delete: { daysAfterModificationGreaterThan: retentionDays } } } }
        }
      ]
    }
  }
}

resource blobAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for grant in grants: {
    name: guid(storage.id, grant.id, roles.blobContributor)
    scope: storage
    properties: { roleDefinitionId: roleId(roles.blobContributor), principalId: grant.id, principalType: grant.type }
  }
]

resource vault 'Microsoft.KeyVault/vaults@2026-05-15' = {
  name: 'kv-elevant-${short}-swc'
  location: location
  tags: tags
  properties: {
    tenantId: tenant().tenantId, sku: { family: 'A', name: 'standard' }, enableRbacAuthorization: true
    enableSoftDelete: true, softDeleteRetentionInDays: 7, enablePurgeProtection: true
  }
}

output cosmosEndpoint string = cosmos.properties.documentEndpoint
output blobEndpoint string = storage.properties.primaryEndpoints.blob
