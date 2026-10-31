param short string
param amount int
@secure()
param alertEmail string
@description('First month of the budget, fixed so that a redeployment never changes it.')
param startDate string = '2026-11-01'

var levels = [
  { name: 'actual-50', threshold: 50, kind: 'Actual' }
  { name: 'actual-80', threshold: 80, kind: 'Actual' }
  { name: 'actual-100', threshold: 100, kind: 'Actual' }
  { name: 'forecast-100', threshold: 100, kind: 'Forecasted' }
]

resource budget 'Microsoft.Consumption/budgets@2026-06-01' = {
  name: 'budget-elevant-${short}'
  properties: {
    category: 'Cost', amount: amount, timeGrain: 'Monthly', timePeriod: { startDate: startDate }
    notifications: toObject(levels, level => level.name, level => {
      enabled: true, operator: 'GreaterThanOrEqualTo', threshold: level.threshold, thresholdType: level.kind, contactEmails: [alertEmail]
    })
  }
}
