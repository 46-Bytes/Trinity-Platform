// Trinity Platform — Azure infrastructure
// Deploy into an existing resource group:
//   az deployment group create -g <rg> -f infra/main.bicep -p infra/main.parameters.json
targetScope = 'resourceGroup'

@description('Short name used as a prefix for all resources, e.g. "trinity"')
param namePrefix string = 'trinity'

@description('Deployment environment suffix, e.g. dev / staging / prod')
param envName string = 'prod'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Container image for the API+worker service (updated by CI after each build)')
param apiImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

@secure()
@description('Postgres administrator password')
param postgresAdminPassword string

@secure()
param secretKey string
@secure()
param auth0ClientSecret string
@secure()
param auth0ManagementClientSecret string
@secure()
param anthropicApiKey string
@secure()
param openaiApiKey string = ''
@secure()
param resendApiKey string = ''

@description('Auth0 / app config — non-secret values')
param auth0Domain string
param auth0ClientId string
param auth0Audience string
param auth0ManagementApiAudience string
param auth0ManagementClientId string
param frontendUrl string

var resourceToken = uniqueString(resourceGroup().id, envName)
var tags = {
  project: 'trinity-platform'
  environment: envName
}

// ---------- Observability ----------
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: '${namePrefix}-log-${resourceToken}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${namePrefix}-ai-${resourceToken}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ---------- Container Registry ----------
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: '${namePrefix}acr${resourceToken}'
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: true
  }
}

// ---------- Key Vault ----------
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: '${namePrefix}-kv-${resourceToken}'
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
  }
}

// ---------- Storage (Blob for uploads/exports/templates) ----------
resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '${namePrefix}st${resourceToken}'
  location: location
  tags: tags
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storage
  name: 'default'
}

resource filesContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'files'
  properties: {
    publicAccess: 'None'
  }
}

// ---------- Redis (Celery broker/result backend) ----------
resource redis 'Microsoft.Cache/redis@2023-08-01' = {
  name: '${namePrefix}-redis-${resourceToken}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'Basic'
      family: 'C'
      capacity: 0
    }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
  }
}

// ---------- Postgres Flexible Server ----------
resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = {
  name: '${namePrefix}-pg-${resourceToken}'
  location: location
  tags: tags
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: 'trinityadmin'
    administratorLoginPassword: postgresAdminPassword
    storage: { storageSizeGB: 32 }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: { mode: 'Disabled' }
  }
}

resource postgresDb 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-06-01-preview' = {
  parent: postgres
  name: 'trinity'
}

// Allow Azure services (Container Apps outbound IPs) through the firewall.
resource postgresFirewallAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-06-01-preview' = {
  parent: postgres
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// ---------- Container Apps Environment ----------
resource containerAppEnv 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: '${namePrefix}-env-${resourceToken}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

var databaseUrl = 'postgresql://trinityadmin:${postgresAdminPassword}@${postgres.properties.fullyQualifiedDomainName}:5432/trinity'
var redisUrl = 'rediss://:${redis.listKeys().primaryKey}@${redis.properties.hostName}:${redis.properties.sslPort}/0'
var storageConnectionString = 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'

var commonSecrets = [
  { name: 'database-url', value: databaseUrl }
  { name: 'redis-url', value: redisUrl }
  { name: 'storage-connection-string', value: storageConnectionString }
  { name: 'secret-key', value: secretKey }
  { name: 'auth0-client-secret', value: auth0ClientSecret }
  { name: 'auth0-mgmt-client-secret', value: auth0ManagementClientSecret }
  { name: 'anthropic-api-key', value: anthropicApiKey }
  { name: 'openai-api-key', value: openaiApiKey }
  { name: 'resend-api-key', value: resendApiKey }
  { name: 'acr-password', value: acr.listCredentials().passwords[0].value }
]

var commonEnv = [
  { name: 'APP_ENV', value: envName }
  { name: 'DEBUG', value: 'false' }
  { name: 'DATABASE_URL', secretRef: 'database-url' }
  { name: 'CELERY_BROKER_URL', secretRef: 'redis-url' }
  { name: 'CELERY_RESULT_BACKEND', secretRef: 'redis-url' }
  { name: 'STORAGE_BACKEND', value: 'azure_blob' }
  { name: 'AZURE_STORAGE_CONNECTION_STRING', secretRef: 'storage-connection-string' }
  { name: 'AZURE_STORAGE_CONTAINER', value: 'files' }
  { name: 'SECRET_KEY', secretRef: 'secret-key' }
  { name: 'AUTH0_DOMAIN', value: auth0Domain }
  { name: 'AUTH0_CLIENT_ID', value: auth0ClientId }
  { name: 'AUTH0_CLIENT_SECRET', secretRef: 'auth0-client-secret' }
  { name: 'AUTH0_AUDIENCE', value: auth0Audience }
  { name: 'AUTH0_MANAGEMENT_API_AUDIENCE', value: auth0ManagementApiAudience }
  { name: 'AUTH0_MANAGEMENT_CLIENT_ID', value: auth0ManagementClientId }
  { name: 'AUTH0_MANAGEMENT_CLIENT_SECRET', secretRef: 'auth0-mgmt-client-secret' }
  { name: 'FRONTEND_URL', value: frontendUrl }
  { name: 'ANTHROPIC_API_KEY', secretRef: 'anthropic-api-key' }
  { name: 'OPENAI_API_KEY', secretRef: 'openai-api-key' }
  { name: 'RESEND_API_KEY', secretRef: 'resend-api-key' }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
]

var registryLoginServer = acr.properties.loginServer

// ---------- API + Celery worker container app (single app, external ingress) ----------
// Both processes run in one container (supervisord starts gunicorn and the
// Celery worker together — see backend/Dockerfile, backend/supervisord.conf).
// This trades independent scaling/fault isolation between API and worker
// for roughly half the always-on compute cost of running them as two
// separate Container Apps; see infra/README.md for the trade-off.
resource apiApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: '${namePrefix}-api-${resourceToken}'
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
      }
      registries: [
        {
          server: registryLoginServer
          username: acr.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: commonSecrets
    }
    template: {
      containers: [
        {
          name: 'api'
          image: apiImage
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: commonEnv
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 8000 }
              initialDelaySeconds: 15
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
        rules: [
          {
            name: 'http-scale'
            http: { metadata: { concurrentRequests: '50' } }
          }
        ]
      }
    }
  }
}

output acrLoginServer string = registryLoginServer
output apiFqdn string = apiApp.properties.configuration.ingress.fqdn
output storageAccountName string = storage.name
output keyVaultName string = keyVault.name
output postgresHost string = postgres.properties.fullyQualifiedDomainName
output redisHost string = redis.properties.hostName
