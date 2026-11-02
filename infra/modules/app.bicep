param location string
param tags object
param short string
@description('Production keeps several revisions for blue/green; staging keeps one (ADR-009).')
param production bool
param image string
param registryServer string
@description('Resource id of id-elevant-<env>, which pulls the image and calls every dependency.')
param identityId string
param revisionSuffix string
param stableRevision string
param maxReplicas int
param authClientId string
@description('Resource id of cae-elevant-env, the Container Apps environment both apps join, owned by production (ADR-016).')
param environmentId string
@description('Environment variables of the container.')
param settings object

var name = 'ca-elevant-${short}'
var revision = '${name}--${revisionSuffix}'
var green = { revisionName: revision, weight: empty(stableRevision) ? 100 : 0, label: 'green' }
var blueGreen = empty(stableRevision) ? [green] : [{ revisionName: stableRevision, weight: 100, label: 'blue' }, green]
var issuer = '${environment().authentication.loginEndpoint}${tenant().tenantId}/v2.0'

resource app 'Microsoft.App/containerApps@2026-07-01' = {
  name: name
  location: location
  tags: tags
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identityId}': {} } }
  properties: {
    environmentId: environmentId
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: production ? 'Multiple' : 'Single'
      maxInactiveRevisions: 5
      ingress: {
        external: true, targetPort: 8000, transport: 'auto', allowInsecure: false
        traffic: production ? blueGreen : [{ latestRevision: true, weight: 100 }]
      }
      registries: [{ server: registryServer, identity: identityId }]
    }
    template: {
      revisionSuffix: revisionSuffix
      containers: [
        {
          name: 'elevant'
          image: image
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [for item in items(settings): { name: item.key, value: item.value }]
          probes: [
            for kind in ['Startup', 'Liveness', 'Readiness']: {
              type: kind, httpGet: { path: '/healthz', port: 8000 }, periodSeconds: kind == 'Startup' ? 5 : 10, failureThreshold: kind == 'Startup' ? 24 : 3
            }
          ]
        }
      ]
      scale: { minReplicas: 0, maxReplicas: maxReplicas, rules: [{ name: 'http', http: { metadata: { concurrentRequests: '10' } } }] }
    }
  }
}

resource auth 'Microsoft.App/containerApps/authConfigs@2026-07-01' = {
  parent: app
  name: 'current'
  properties: {
    platform: { enabled: true }
    globalValidation: {
      unauthenticatedClientAction: 'RedirectToLoginPage', redirectToProvider: 'azureactivedirectory', excludedPaths: ['/healthz', '/api/version']
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true, registration: { clientId: authClientId, openIdIssuer: issuer }, validation: { allowedAudiences: ['api://${authClientId}'] }
      }
    }
    httpSettings: { requireHttps: true }
  }
}

output name string = app.name
output revision string = revision
