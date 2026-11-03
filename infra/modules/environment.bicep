@description('The one Container Apps environment of Elevant, shared by staging and production and owned by production (ADR-016), in Spain Central (ADR-017).')
param name string
param location string
param tags object
@description('Resource id of production\'s workspace, which receives the environment\'s container logs of both apps.')
param workspaceId string

resource managed 'Microsoft.App/managedEnvironments@2026-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: { destination: 'azure-monitor' }, workloadProfiles: [{ name: 'Consumption', workloadProfileType: 'Consumption' }], zoneRedundant: false
  }
}

#disable-next-line use-recent-api-versions
resource logs 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'to-workspace'
  scope: managed
  properties: { workspaceId: workspaceId, logs: [{ categoryGroup: 'allLogs', enabled: true }] }
}

output id string = managed.id
