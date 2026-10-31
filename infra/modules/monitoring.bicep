import { roles, roleId } from 'roles.bicep'

param location string
param tags object
param short string
@description('The SLO alert and its action group exist in production only: each log alert rule bills (ADR-011).')
param production bool
param dailyCapGb string
@description('Principal id of the app identity, which sends telemetry with Entra ID.')
param principalId string
@secure()
param alertEmail string

var slos = '''
union
  (requests
    | extend local = datetime_utc_to_local(timestamp, "Europe/Madrid")
    | where dayofweek(local) between (1d .. 5d) and hourofday(local) between (7 .. 19)
    | summarize n = count(), value = 100.0 * countif(toint(resultCode) < 500) / count()
    | where n >= 20 and value < 99.7 | extend slo = "availability_pct"),
  (customEvents | where name == "quote_drafted"
    | summarize n = count(), value = percentile(todouble(customDimensions.duration_ms), 95) / 1000
    | where n >= 3 and value > 45 | extend slo = "draft_p95_s"),
  (customEvents | where name in ("quote_drafted", "quote_failed")
    | summarize n = count(), value = 100.0 * countif(name == "quote_failed") / count()
    | where value >= 1 | extend slo = "failed_drafts_pct")
'''

resource workspace 'Microsoft.OperationalInsights/workspaces@2026-03-01' = {
  name: 'log-elevant-${short}-swc'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }, retentionInDays: 31, workspaceCapping: { dailyQuotaGb: json(dailyCapGb) }, features: { disableLocalAuth: true }
  }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-elevant-${short}-swc'
  location: location
  tags: tags
  kind: 'web'
  properties: { Application_Type: 'web', WorkspaceResourceId: workspace.id, DisableLocalAuth: true, IngestionMode: 'LogAnalytics' }
}

resource publisher 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(insights.id, principalId, roles.metricsPublisher)
  scope: insights
  properties: { roleDefinitionId: roleId(roles.metricsPublisher), principalId: principalId, principalType: 'ServicePrincipal' }
}

resource workbook 'Microsoft.Insights/workbooks@2023-06-01' = {
  name: guid(insights.id, 'elevant-workbook')
  location: location
  tags: tags
  kind: 'shared'
  properties: {
    displayName: 'Elevant: KPIs, SLOs and health (${short})', category: 'workbook', sourceId: insights.id
    serializedData: string(union(loadJsonContent('../workbook.json'), { fallbackResourceIds: [insights.id] }))
  }
}

resource group 'Microsoft.Insights/actionGroups@2023-01-01' = if (production) {
  name: 'ag-elevant-${short}-swc'
  location: 'global'
  tags: tags
  properties: { groupShortName: 'elevant', enabled: true, emailReceivers: [{ name: 'owner', emailAddress: alertEmail, useCommonAlertSchema: true }] }
}

resource sloAlert 'Microsoft.Insights/scheduledQueryRules@2026-03-01' = if (production) {
  name: 'alert-elevant-slo-${short}'
  location: location
  tags: tags
  properties: {
    description: 'An Elevant SLO is breached over the last hour: availability in business hours, draft p95 or failed drafts.'
    severity: 2, enabled: true, scopes: [insights.id], evaluationFrequency: 'PT15M', windowSize: 'PT1H', autoMitigate: true
    criteria: {
      allOf: [
        {
          query: slos, timeAggregation: 'Count', dimensions: [{ name: 'slo', operator: 'Include', values: ['*'] }]
          operator: 'GreaterThan', threshold: 0, failingPeriods: { numberOfEvaluationPeriods: 1, minFailingPeriodsToAlert: 1 }
        }
      ]
    }
    actions: { actionGroups: [group.id] }
  }
}

output connectionString string = insights.properties.ConnectionString
output workspaceId string = workspace.id
