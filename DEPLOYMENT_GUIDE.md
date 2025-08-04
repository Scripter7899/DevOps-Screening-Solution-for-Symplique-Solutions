# Deployment Guide

## Overview

This comprehensive deployment guide provides step-by-step instructions for implementing the Azure Billing Records Cost Optimization Solution in production environments. The guide covers prerequisites, infrastructure setup, application deployment, configuration, testing, and operational procedures.

## Prerequisites

### Azure Subscription Requirements

Before beginning the deployment process, ensure that your Azure subscription meets the following requirements:

**Subscription Permissions**: The deploying user must have Owner or Contributor permissions on the target Azure subscription. These permissions are required to create resource groups, deploy Azure services, and configure service-to-service authentication using managed identities.

**Resource Quotas**: Verify that your subscription has sufficient quota for the required Azure services. The solution requires quota for Azure Cosmos DB accounts, Azure Storage accounts, Azure Function Apps, and associated networking resources. Contact Azure support if quota increases are needed.

**Service Availability**: Confirm that all required Azure services are available in your target deployment region. The solution requires Azure Cosmos DB, Azure Blob Storage, Azure Functions, Azure Monitor, and Azure Key Vault. Some Azure services may have limited regional availability.

### Development Environment Setup

**Azure CLI Installation**: Install the latest version of Azure CLI (version 2.40.0 or later) on your deployment machine. The Azure CLI is used for infrastructure deployment and configuration management. Verify installation by running `az --version` and ensure you can authenticate to your Azure subscription using `az login`.

**Python Environment**: Install Python 3.11 or later with pip package manager. The solution includes Python-based Azure Functions and deployment scripts that require a compatible Python environment. Consider using virtual environments to isolate dependencies and avoid conflicts with other Python projects.

**Azure Functions Core Tools**: Install Azure Functions Core Tools version 4.x for local development and deployment of Azure Functions. This tool is essential for packaging and deploying the archival and retrieval functions to Azure.

**Git Version Control**: Ensure Git is installed and configured for version control and deployment automation. The deployment process includes Git-based deployment options for Azure Functions.

### Network and Security Prerequisites

**Network Configuration**: Plan your network architecture, including virtual network configuration, subnet allocation, and network security group rules. The solution can be deployed with public endpoints for simplicity or with private endpoints for enhanced security.

**SSL Certificates**: If using custom domains, ensure that valid SSL certificates are available and properly configured. Azure provides managed certificates for Azure-hosted domains, or you can use certificates from external certificate authorities.

**Firewall and Proxy Configuration**: If deploying from a corporate environment, ensure that firewall and proxy configurations allow access to Azure services and deployment endpoints. The deployment process requires outbound HTTPS access to Azure management endpoints.

## Infrastructure Deployment

### Automated Deployment

The solution includes automated deployment scripts that create and configure all required Azure resources. The automated deployment approach is recommended for most scenarios as it ensures consistent configuration and reduces deployment time.

**Configuration Setup**: Begin by creating a deployment configuration file that specifies your deployment parameters. Copy the provided `deployment_config.json.example` file to `deployment_config.json` and update the values according to your requirements:

```json
{
  "project_name": "billing-optimization",
  "resource_group": "billing-optimization-rg",
  "location": "East US",
  "subscription_id": "your-subscription-id-here",
  "environment": "production",
  "cosmos_db": {
    "account_name": "billing-optimization-cosmos",
    "database_name": "billing",
    "container_name": "records",
    "throughput_min": 400,
    "throughput_max": 4000
  },
  "storage": {
    "account_name": "billingoptimizationstorage",
    "container_name": "archived-billing-records",
    "default_tier": "Cool"
  },
  "functions": {
    "app_name": "billing-optimization-functions",
    "storage_account": "billingoptfuncstorage"
  }
}
```

**Resource Group Creation**: The deployment process begins with creating an Azure resource group that will contain all solution components. Resource groups provide a logical container for related resources and enable unified management, monitoring, and access control.

Execute the deployment script to create the resource group:

```bash
python deployment_scripts.py --create-resource-group
```

The script will create the resource group in the specified location and configure appropriate tags for resource management and cost tracking.

**Azure Cosmos DB Deployment**: The next step involves deploying Azure Cosmos DB with optimized configuration for the billing records workload. The deployment script creates a Cosmos DB account with the following optimizations:

- **Consistency Level**: Session consistency provides the optimal balance between performance and data consistency for the billing records use case
- **Automatic Failover**: Enabled to provide high availability and disaster recovery capabilities
- **Throughput Configuration**: Autoscale throughput with configurable minimum and maximum RU/s settings
- **Indexing Policy**: Optimized indexing policy that includes only necessary fields to minimize RU consumption

Execute the Cosmos DB deployment:

```bash
python deployment_scripts.py --deploy-cosmos-db
```

The deployment process includes creating the database and container with the optimized indexing policy. The script will output the Cosmos DB endpoint and access keys required for application configuration.

**Azure Storage Account Deployment**: Deploy the Azure Storage account that will serve as the cold storage tier for archived billing records. The storage account is configured with the following optimizations:

- **Storage Tier**: Cool tier as the default for cost optimization
- **Replication**: Locally redundant storage (LRS) or geo-redundant storage (GRS) based on requirements
- **Lifecycle Management**: Automated policies for tier transitions and data retention
- **Security**: Encryption at rest with service-managed keys

Execute the storage account deployment:

```bash
python deployment_scripts.py --deploy-storage
```

The deployment script creates the storage account and blob container with appropriate access policies and lifecycle management rules.

**Azure Functions Deployment**: Deploy the Azure Function App that hosts the archival and retrieval functions. The Function App is configured with the following settings:

- **Hosting Plan**: Consumption plan for cost optimization and automatic scaling
- **Runtime**: Python 3.11 runtime with Azure Functions v4
- **Application Settings**: Environment variables for service connections and configuration
- **Managed Identity**: System-assigned managed identity for secure service-to-service authentication

Execute the Function App deployment:

```bash
python deployment_scripts.py --deploy-functions
```

The deployment script creates the Function App and configures the necessary application settings for connecting to Cosmos DB and Blob Storage.

### Manual Deployment

For organizations that require manual deployment processes or custom configurations, the solution can be deployed using Azure CLI commands or Azure Resource Manager (ARM) templates.

**Resource Group Creation**: Create the resource group manually using Azure CLI:

```bash
az group create \
  --name billing-optimization-rg \
  --location "East US" \
  --tags environment=production project=billing-optimization
```

**Cosmos DB Manual Deployment**: Create the Cosmos DB account with optimized settings:

```bash
# Create Cosmos DB account
az cosmosdb create \
  --name billing-optimization-cosmos \
  --resource-group billing-optimization-rg \
  --locations regionName="East US" \
  --default-consistency-level Session \
  --enable-automatic-failover true

# Create database
az cosmosdb sql database create \
  --account-name billing-optimization-cosmos \
  --resource-group billing-optimization-rg \
  --name billing

# Create container with optimized indexing
az cosmosdb sql container create \
  --account-name billing-optimization-cosmos \
  --resource-group billing-optimization-rg \
  --database-name billing \
  --name records \
  --partition-key-path "/id" \
  --throughput 400 \
  --idx @indexing-policy.json
```

**Storage Account Manual Deployment**: Create the storage account and configure lifecycle management:

```bash
# Create storage account
az storage account create \
  --name billingoptimizationstorage \
  --resource-group billing-optimization-rg \
  --location "East US" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --access-tier Cool

# Create blob container
az storage container create \
  --name archived-billing-records \
  --account-name billingoptimizationstorage \
  --resource-group billing-optimization-rg
```

**Function App Manual Deployment**: Create the Function App and configure settings:

```bash
# Create storage account for Function App
az storage account create \
  --name billingoptfuncstorage \
  --resource-group billing-optimization-rg \
  --location "East US" \
  --sku Standard_LRS

# Create Function App
az functionapp create \
  --name billing-optimization-functions \
  --resource-group billing-optimization-rg \
  --storage-account billingoptfuncstorage \
  --consumption-plan-location "East US" \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4
```

## Application Deployment

### Function App Deployment

The application deployment process involves packaging and deploying the Azure Functions code to the Function App created during infrastructure deployment.

**Code Preparation**: Ensure that all function code and dependencies are properly prepared for deployment. The solution includes the following function components:

- `archival_function.py`: Scheduled function for data archival
- `retrieval_function.py`: HTTP-triggered function for data retrieval
- `function_app.py`: Function App configuration and routing
- `requirements.txt`: Python dependencies
- `host.json`: Function App host configuration

**Dependency Installation**: Install the required Python dependencies locally to verify compatibility:

```bash
pip install -r requirements.txt
```

Verify that all dependencies install successfully and are compatible with the Azure Functions Python runtime.

**Function Deployment**: Deploy the functions using Azure Functions Core Tools:

```bash
# Navigate to the project directory
cd azure-billing-cost-optimization

# Deploy functions to Azure
func azure functionapp publish billing-optimization-functions
```

The deployment process packages the function code and dependencies, uploads them to Azure, and configures the function triggers and bindings.

**Configuration Verification**: After deployment, verify that the function configuration is correct:

```bash
# List function app settings
az functionapp config appsettings list \
  --name billing-optimization-functions \
  --resource-group billing-optimization-rg

# Test function endpoints
curl https://billing-optimization-functions.azurewebsites.net/api/retrieve?id=test-record
```

### Service Deployment

Deploy the main billing service that provides API compatibility and intelligent routing between storage tiers.

**Service Configuration**: Configure the billing service with the appropriate connection strings and endpoints. Update the service configuration file with the values from your Azure deployment:

```python
# Configuration from Azure deployment
COSMOS_ENDPOINT = "https://billing-optimization-cosmos.documents.azure.com:443/"
COSMOS_KEY = "your-cosmos-key-here"
BLOB_CONNECTION_STRING = "your-blob-connection-string-here"
RETRIEVAL_FUNCTION_URL = "https://billing-optimization-functions.azurewebsites.net/api/retrieve"
```

**Container Deployment**: If deploying the service as a container, build and deploy the Docker image:

```bash
# Build Docker image
docker build -t billing-service:latest .

# Tag for Azure Container Registry
docker tag billing-service:latest your-registry.azurecr.io/billing-service:latest

# Push to registry
docker push your-registry.azurecr.io/billing-service:latest

# Deploy to Azure Container Instances or Azure Kubernetes Service
az container create \
  --resource-group billing-optimization-rg \
  --name billing-service \
  --image your-registry.azurecr.io/billing-service:latest \
  --ports 5000 \
  --environment-variables \
    COSMOS_ENDPOINT="https://billing-optimization-cosmos.documents.azure.com:443/" \
    COSMOS_KEY="your-cosmos-key-here"
```

**App Service Deployment**: Alternatively, deploy the service to Azure App Service:

```bash
# Create App Service plan
az appservice plan create \
  --name billing-service-plan \
  --resource-group billing-optimization-rg \
  --sku B1 \
  --is-linux

# Create web app
az webapp create \
  --resource-group billing-optimization-rg \
  --plan billing-service-plan \
  --name billing-optimization-service \
  --runtime "PYTHON|3.11"

# Deploy code
az webapp deployment source config-zip \
  --resource-group billing-optimization-rg \
  --name billing-optimization-service \
  --src billing-service.zip
```

## Configuration Management

### Environment Variables

Proper configuration management is critical for security and operational efficiency. The solution uses environment variables for configuration, which should be managed securely using Azure Key Vault or Azure App Configuration.

**Cosmos DB Configuration**: Configure the connection to Azure Cosmos DB:

```bash
# Set Cosmos DB configuration
az functionapp config appsettings set \
  --name billing-optimization-functions \
  --resource-group billing-optimization-rg \
  --settings \
    COSMOS_ENDPOINT="https://billing-optimization-cosmos.documents.azure.com:443/" \
    COSMOS_KEY="@Microsoft.KeyVault(SecretUri=https://your-keyvault.vault.azure.net/secrets/cosmos-key/)" \
    COSMOS_DATABASE_NAME="billing" \
    COSMOS_CONTAINER_NAME="records"
```

**Storage Configuration**: Configure the connection to Azure Blob Storage:

```bash
# Set storage configuration
az functionapp config appsettings set \
  --name billing-optimization-functions \
  --resource-group billing-optimization-rg \
  --settings \
    BLOB_CONNECTION_STRING="@Microsoft.KeyVault(SecretUri=https://your-keyvault.vault.azure.net/secrets/storage-connection/)" \
    BLOB_CONTAINER_NAME="archived-billing-records"
```

**Archival Configuration**: Configure the archival process parameters:

```bash
# Set archival configuration
az functionapp config appsettings set \
  --name billing-optimization-functions \
  --resource-group billing-optimization-rg \
  --settings \
    ARCHIVE_THRESHOLD_MONTHS="3" \
    BATCH_SIZE="100" \
    ARCHIVAL_SCHEDULE="0 0 2 * * *"
```

### Security Configuration

**Managed Identity Setup**: Configure managed identity for secure service-to-service authentication:

```bash
# Enable system-assigned managed identity
az functionapp identity assign \
  --name billing-optimization-functions \
  --resource-group billing-optimization-rg

# Grant permissions to Cosmos DB
az cosmosdb sql role assignment create \
  --account-name billing-optimization-cosmos \
  --resource-group billing-optimization-rg \
  --scope "/" \
  --principal-id "managed-identity-principal-id" \
  --role-definition-id "00000000-0000-0000-0000-000000000002"

# Grant permissions to Storage Account
az role assignment create \
  --assignee "managed-identity-principal-id" \
  --role "Storage Blob Data Contributor" \
  --scope "/subscriptions/subscription-id/resourceGroups/billing-optimization-rg/providers/Microsoft.Storage/storageAccounts/billingoptimizationstorage"
```

**Key Vault Integration**: Configure Azure Key Vault for secure secret management:

```bash
# Create Key Vault
az keyvault create \
  --name billing-optimization-kv \
  --resource-group billing-optimization-rg \
  --location "East US"

# Store secrets
az keyvault secret set \
  --vault-name billing-optimization-kv \
  --name cosmos-key \
  --value "your-cosmos-key-here"

az keyvault secret set \
  --vault-name billing-optimization-kv \
  --name storage-connection \
  --value "your-storage-connection-string-here"

# Grant Function App access to Key Vault
az keyvault set-policy \
  --name billing-optimization-kv \
  --object-id "function-app-managed-identity-id" \
  --secret-permissions get list
```

### Monitoring Configuration

**Application Insights Setup**: Configure Application Insights for comprehensive monitoring:

```bash
# Create Application Insights
az monitor app-insights component create \
  --app billing-optimization-insights \
  --location "East US" \
  --resource-group billing-optimization-rg \
  --application-type web

# Configure Function App to use Application Insights
az functionapp config appsettings set \
  --name billing-optimization-functions \
  --resource-group billing-optimization-rg \
  --settings \
    APPINSIGHTS_INSTRUMENTATIONKEY="your-instrumentation-key-here" \
    APPLICATIONINSIGHTS_CONNECTION_STRING="your-connection-string-here"
```

**Log Analytics Workspace**: Create a Log Analytics workspace for centralized logging:

```bash
# Create Log Analytics workspace
az monitor log-analytics workspace create \
  --resource-group billing-optimization-rg \
  --workspace-name billing-optimization-logs \
  --location "East US"

# Configure diagnostic settings
az monitor diagnostic-settings create \
  --name billing-optimization-diagnostics \
  --resource "/subscriptions/subscription-id/resourceGroups/billing-optimization-rg/providers/Microsoft.DocumentDB/databaseAccounts/billing-optimization-cosmos" \
  --workspace "/subscriptions/subscription-id/resourceGroups/billing-optimization-rg/providers/Microsoft.OperationalInsights/workspaces/billing-optimization-logs" \
  --logs '[{"category":"DataPlaneRequests","enabled":true}]' \
  --metrics '[{"category":"Requests","enabled":true}]'
```

## Testing and Validation

### Functional Testing

Comprehensive testing is essential to ensure that the solution operates correctly and meets all requirements. The testing process includes unit tests, integration tests, and end-to-end validation.

**Unit Testing**: Execute unit tests for individual components:

```bash
# Install testing dependencies
pip install pytest pytest-asyncio

# Run unit tests
pytest tests/unit/ -v

# Run tests with coverage
pytest tests/unit/ --cov=src --cov-report=html
```

**Integration Testing**: Test the integration between system components:

```bash
# Test Cosmos DB connectivity
python tests/integration/test_cosmos_integration.py

# Test Blob Storage connectivity
python tests/integration/test_storage_integration.py

# Test Function App deployment
python tests/integration/test_function_integration.py
```

**API Testing**: Validate API functionality and compatibility:

```bash
# Test record creation
curl -X POST https://billing-optimization-service.azurewebsites.net/billing/records \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"12345","amount":99.99,"currency":"USD"}'

# Test record retrieval
curl https://billing-optimization-service.azurewebsites.net/billing/records/test-record-id

# Test batch operations
curl -X POST https://billing-optimization-service.azurewebsites.net/billing/records/batch \
  -H "Content-Type: application/json" \
  -d '{"ids":["record1","record2","record3"]}'
```

### Performance Testing

**Load Testing**: Validate system performance under expected load conditions:

```bash
# Install load testing tools
pip install locust

# Run load tests
locust -f tests/performance/load_test.py --host=https://billing-optimization-service.azurewebsites.net

# Monitor performance metrics during testing
az monitor metrics list \
  --resource "/subscriptions/subscription-id/resourceGroups/billing-optimization-rg/providers/Microsoft.DocumentDB/databaseAccounts/billing-optimization-cosmos" \
  --metric "TotalRequestUnits" \
  --interval PT1M
```

**Archival Performance Testing**: Test the archival process with sample data:

```bash
# Create test data
python tests/performance/create_test_data.py --records=10000

# Trigger archival function
az functionapp function invoke \
  --name billing-optimization-functions \
  --resource-group billing-optimization-rg \
  --function-name archival_timer

# Monitor archival progress
az functionapp logs tail \
  --name billing-optimization-functions \
  --resource-group billing-optimization-rg
```

### Security Testing

**Authentication Testing**: Validate authentication and authorization mechanisms:

```bash
# Test API authentication
curl -H "Authorization: Bearer invalid-token" \
  https://billing-optimization-service.azurewebsites.net/billing/records/test-record

# Test managed identity authentication
az functionapp function invoke \
  --name billing-optimization-functions \
  --resource-group billing-optimization-rg \
  --function-name retrieve_record \
  --data '{"id":"test-record"}'
```

**Network Security Testing**: Validate network security configurations:

```bash
# Test private endpoint connectivity
nslookup billing-optimization-cosmos.documents.azure.com

# Test network security group rules
az network nsg rule list \
  --resource-group billing-optimization-rg \
  --nsg-name billing-optimization-nsg
```

## Production Deployment

### Pre-Production Validation

Before deploying to production, complete a comprehensive validation process in a staging environment that mirrors the production configuration.

**Staging Environment Setup**: Create a staging environment with identical configuration to production:

```bash
# Deploy to staging resource group
python deployment_scripts.py --environment=staging --resource-group=billing-optimization-staging-rg
```

**Data Migration Testing**: Test the data migration process with production-like data volumes:

```bash
# Create staging data that mirrors production
python tests/staging/create_staging_data.py --volume=production

# Execute archival process
python tests/staging/test_archival_process.py

# Validate data integrity
python tests/staging/validate_data_integrity.py
```

**Performance Validation**: Validate performance characteristics under production-like conditions:

```bash
# Execute performance tests
python tests/staging/performance_validation.py

# Monitor resource utilization
az monitor metrics list --resource-group billing-optimization-staging-rg
```

### Production Deployment Process

**Blue-Green Deployment**: Implement blue-green deployment to minimize downtime and enable rapid rollback:

```bash
# Deploy to green environment
python deployment_scripts.py --environment=production-green

# Validate green environment
python tests/production/validate_deployment.py --environment=green

# Switch traffic to green environment
az network traffic-manager endpoint update \
  --resource-group billing-optimization-rg \
  --profile-name billing-optimization-tm \
  --name green-endpoint \
  --endpoint-status Enabled

# Disable blue environment
az network traffic-manager endpoint update \
  --resource-group billing-optimization-rg \
  --profile-name billing-optimization-tm \
  --name blue-endpoint \
  --endpoint-status Disabled
```

**Gradual Rollout**: Implement gradual rollout to minimize risk:

```bash
# Route 10% of traffic to new deployment
az network traffic-manager endpoint update \
  --resource-group billing-optimization-rg \
  --profile-name billing-optimization-tm \
  --name new-endpoint \
  --weight 10

# Monitor metrics and gradually increase traffic
# Increase to 50% after validation
az network traffic-manager endpoint update \
  --weight 50

# Complete rollout after full validation
az network traffic-manager endpoint update \
  --weight 100
```

### Post-Deployment Validation

**Functional Validation**: Verify that all functionality operates correctly in production:

```bash
# Execute production validation tests
python tests/production/functional_validation.py

# Validate API endpoints
python tests/production/api_validation.py

# Test archival and retrieval processes
python tests/production/archival_validation.py
```

**Performance Monitoring**: Monitor system performance immediately after deployment:

```bash
# Monitor key performance metrics
az monitor metrics list \
  --resource "/subscriptions/subscription-id/resourceGroups/billing-optimization-rg" \
  --metric "ResponseTime,ThroughputRequests,ErrorRate" \
  --interval PT1M \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)

# Set up alerts for performance degradation
az monitor metrics alert create \
  --name "High Response Time Alert" \
  --resource-group billing-optimization-rg \
  --condition "avg ResponseTime > 5000" \
  --description "Alert when average response time exceeds 5 seconds"
```

**Cost Monitoring**: Verify that cost optimization objectives are being achieved:

```bash
# Monitor cost metrics
az consumption usage list \
  --start-date $(date -u -d '1 day ago' +%Y-%m-%d) \
  --end-date $(date -u +%Y-%m-%d)

# Set up cost alerts
az consumption budget create \
  --resource-group billing-optimization-rg \
  --budget-name "Monthly Budget Alert" \
  --amount 1000 \
  --time-grain Monthly \
  --start-date $(date -u +%Y-%m-01) \
  --end-date $(date -u -d '+1 year' +%Y-%m-01)
```

## Operational Procedures

### Monitoring and Alerting

**Health Monitoring**: Implement comprehensive health monitoring for all system components:

```bash
# Create health check endpoints
az functionapp function create \
  --name billing-optimization-functions \
  --resource-group billing-optimization-rg \
  --function-name health_check \
  --template "HTTP trigger"

# Configure health check monitoring
az monitor action-group create \
  --name billing-optimization-alerts \
  --resource-group billing-optimization-rg \
  --short-name "BillingOpt"

# Set up availability tests
az monitor app-insights web-test create \
  --resource-group billing-optimization-rg \
  --name "API Health Check" \
  --location "East US" \
  --web-test-kind ping \
  --web-test-name "api-health-check" \
  --url "https://billing-optimization-service.azurewebsites.net/health"
```

**Performance Monitoring**: Monitor key performance indicators:

```bash
# Create performance dashboard
az portal dashboard create \
  --resource-group billing-optimization-rg \
  --name "Billing Optimization Dashboard" \
  --input-path dashboard-template.json

# Configure performance alerts
az monitor metrics alert create \
  --name "High RU Consumption" \
  --resource-group billing-optimization-rg \
  --condition "avg TotalRequestUnits > 3000" \
  --description "Alert when Cosmos DB RU consumption is high"
```

### Backup and Recovery

**Automated Backup Configuration**: Configure automated backup for all data:

```bash
# Configure Cosmos DB backup
az cosmosdb update \
  --name billing-optimization-cosmos \
  --resource-group billing-optimization-rg \
  --backup-policy-type Continuous

# Configure blob storage backup
az storage account update \
  --name billingoptimizationstorage \
  --resource-group billing-optimization-rg \
  --enable-versioning true \
  --enable-delete-retention true \
  --delete-retention-days 30
```

**Recovery Testing**: Regularly test recovery procedures:

```bash
# Test point-in-time recovery
az cosmosdb sql database restore \
  --account-name billing-optimization-cosmos \
  --resource-group billing-optimization-rg \
  --target-database-name billing-test-restore \
  --restore-timestamp $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)

# Test blob storage recovery
az storage blob restore \
  --account-name billingoptimizationstorage \
  --time-to-restore $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --source-container archived-billing-records \
  --destination-container archived-billing-records-restored
```

### Maintenance Procedures

**Regular Maintenance Tasks**: Implement regular maintenance procedures:

```bash
# Update function app runtime
az functionapp config set \
  --name billing-optimization-functions \
  --resource-group billing-optimization-rg \
  --python-version 3.11

# Update application dependencies
func azure functionapp publish billing-optimization-functions --build remote

# Review and optimize Cosmos DB indexing
az cosmosdb sql container update \
  --account-name billing-optimization-cosmos \
  --resource-group billing-optimization-rg \
  --database-name billing \
  --name records \
  --idx @updated-indexing-policy.json
```

**Security Updates**: Regularly apply security updates:

```bash
# Update Key Vault access policies
az keyvault set-policy \
  --name billing-optimization-kv \
  --object-id "new-managed-identity-id" \
  --secret-permissions get list

# Rotate access keys
az cosmosdb keys regenerate \
  --name billing-optimization-cosmos \
  --resource-group billing-optimization-rg \
  --key-kind primary

# Update stored secrets
az keyvault secret set \
  --vault-name billing-optimization-kv \
  --name cosmos-key \
  --value "new-cosmos-key-here"
```

This comprehensive deployment guide provides all the necessary information and procedures for successfully implementing the Azure Billing Records Cost Optimization Solution in production environments. Following these procedures ensures a secure, reliable, and cost-effective deployment that meets all operational requirements.

