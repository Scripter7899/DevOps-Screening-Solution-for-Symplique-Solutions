"""
Deployment and Setup Scripts for Azure Billing Cost Optimization Solution.
"""

import json
import os
import subprocess
import logging
from datetime import datetime

class AzureDeploymentManager:
    """
    Manages deployment of the billing cost optimization solution to Azure.
    """
    
    def __init__(self, config):
        self.config = config
        self.resource_group = config.get('resource_group')
        self.location = config.get('location', 'East US')
        self.subscription_id = config.get('subscription_id')
    
    def create_resource_group(self):
        """
        Create Azure resource group if it doesn't exist.
        """
        cmd = [
            'az', 'group', 'create',
            '--name', self.resource_group,
            '--location', self.location
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logging.info(f"Resource group {self.resource_group} created successfully")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to create resource group: {e.stderr}")
            return False
    
    def deploy_cosmos_db(self):
        """
        Deploy Cosmos DB with optimized settings.
        """
        cosmos_config = {
            "account_name": f"{self.config['project_name']}-cosmos",
            "database_name": "billing",
            "container_name": "records",
            "throughput": 400,  # Minimum autoscale
            "max_throughput": 4000
        }
        
        # Create Cosmos DB account
        cmd = [
            'az', 'cosmosdb', 'create',
            '--name', cosmos_config['account_name'],
            '--resource-group', self.resource_group,
            '--locations', f"regionName={self.location}",
            '--default-consistency-level', 'Session',
            '--enable-automatic-failover', 'true'
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            logging.info(f"Cosmos DB account {cosmos_config['account_name']} created")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to create Cosmos DB: {e.stderr}")
            return False
        
        # Create database
        cmd = [
            'az', 'cosmosdb', 'sql', 'database', 'create',
            '--account-name', cosmos_config['account_name'],
            '--resource-group', self.resource_group,
            '--name', cosmos_config['database_name']
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            logging.info(f"Database {cosmos_config['database_name']} created")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to create database: {e.stderr}")
            return False
        
        # Create container with optimized indexing
        indexing_policy = {
            "indexingMode": "consistent",
            "automatic": True,
            "includedPaths": [
                {"path": "/id/?"},
                {"path": "/created_date/?"}
            ],
            "excludedPaths": [
                {"path": "/*"}
            ]
        }
        
        cmd = [
            'az', 'cosmosdb', 'sql', 'container', 'create',
            '--account-name', cosmos_config['account_name'],
            '--resource-group', self.resource_group,
            '--database-name', cosmos_config['database_name'],
            '--name', cosmos_config['container_name'],
            '--partition-key-path', '/id',
            '--throughput', str(cosmos_config['throughput']),
            '--idx', json.dumps(indexing_policy)
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            logging.info(f"Container {cosmos_config['container_name']} created")
            return cosmos_config
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to create container: {e.stderr}")
            return False
    
    def deploy_storage_account(self):
        """
        Deploy storage account with lifecycle management.
        """
        storage_config = {
            "account_name": f"{self.config['project_name']}storage",
            "container_name": "archived-billing-records"
        }
        
        # Create storage account
        cmd = [
            'az', 'storage', 'account', 'create',
            '--name', storage_config['account_name'],
            '--resource-group', self.resource_group,
            '--location', self.location,
            '--sku', 'Standard_LRS',
            '--kind', 'StorageV2',
            '--access-tier', 'Cool'
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            logging.info(f"Storage account {storage_config['account_name']} created")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to create storage account: {e.stderr}")
            return False
        
        # Create blob container
        cmd = [
            'az', 'storage', 'container', 'create',
            '--name', storage_config['container_name'],
            '--account-name', storage_config['account_name'],
            '--resource-group', self.resource_group
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            logging.info(f"Blob container {storage_config['container_name']} created")
            return storage_config
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to create blob container: {e.stderr}")
            return False
    
    def deploy_function_app(self):
        """
        Deploy Azure Function App for archival and retrieval.
        """
        function_config = {
            "app_name": f"{self.config['project_name']}-functions",
            "storage_account": f"{self.config['project_name']}funcstorage"
        }
        
        # Create storage account for function app
        cmd = [
            'az', 'storage', 'account', 'create',
            '--name', function_config['storage_account'],
            '--resource-group', self.resource_group,
            '--location', self.location,
            '--sku', 'Standard_LRS'
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            logging.info(f"Function storage account created")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to create function storage: {e.stderr}")
            return False
        
        # Create function app
        cmd = [
            'az', 'functionapp', 'create',
            '--name', function_config['app_name'],
            '--resource-group', self.resource_group,
            '--storage-account', function_config['storage_account'],
            '--consumption-plan-location', self.location,
            '--runtime', 'python',
            '--runtime-version', '3.11',
            '--functions-version', '4'
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            logging.info(f"Function app {function_config['app_name']} created")
            return function_config
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to create function app: {e.stderr}")
            return False
    
    def configure_app_settings(self, cosmos_config, storage_config, function_config):
        """
        Configure application settings for the function app.
        """
        # Get Cosmos DB connection string
        cmd = [
            'az', 'cosmosdb', 'keys', 'list',
            '--name', cosmos_config['account_name'],
            '--resource-group', self.resource_group,
            '--type', 'keys'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            cosmos_keys = json.loads(result.stdout)
            cosmos_key = cosmos_keys['primaryMasterKey']
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to get Cosmos DB keys: {e.stderr}")
            return False
        
        # Get storage connection string
        cmd = [
            'az', 'storage', 'account', 'show-connection-string',
            '--name', storage_config['account_name'],
            '--resource-group', self.resource_group
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            storage_conn = json.loads(result.stdout)
            storage_connection_string = storage_conn['connectionString']
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to get storage connection string: {e.stderr}")
            return False
        
        # Set application settings
        settings = [
            f"COSMOS_ENDPOINT=https://{cosmos_config['account_name']}.documents.azure.com:443/",
            f"COSMOS_KEY={cosmos_key}",
            f"COSMOS_DATABASE_NAME={cosmos_config['database_name']}",
            f"COSMOS_CONTAINER_NAME={cosmos_config['container_name']}",
            f"BLOB_CONNECTION_STRING={storage_connection_string}",
            f"BLOB_CONTAINER_NAME={storage_config['container_name']}"
        ]
        
        for setting in settings:
            cmd = [
                'az', 'functionapp', 'config', 'appsettings', 'set',
                '--name', function_config['app_name'],
                '--resource-group', self.resource_group,
                '--settings', setting
            ]
            
            try:
                subprocess.run(cmd, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to set app setting {setting}: {e.stderr}")
                return False
        
        logging.info("Application settings configured successfully")
        return True
    
    def deploy_solution(self):
        """
        Deploy the complete solution.
        """
        logging.info("Starting deployment of billing cost optimization solution")
        
        # Create resource group
        if not self.create_resource_group():
            return False
        
        # Deploy Cosmos DB
        cosmos_config = self.deploy_cosmos_db()
        if not cosmos_config:
            return False
        
        # Deploy storage account
        storage_config = self.deploy_storage_account()
        if not storage_config:
            return False
        
        # Deploy function app
        function_config = self.deploy_function_app()
        if not function_config:
            return False
        
        # Configure app settings
        if not self.configure_app_settings(cosmos_config, storage_config, function_config):
            return False
        
        deployment_info = {
            "timestamp": datetime.utcnow().isoformat(),
            "resource_group": self.resource_group,
            "cosmos_db": cosmos_config,
            "storage": storage_config,
            "function_app": function_config,
            "endpoints": {
                "cosmos_endpoint": f"https://{cosmos_config['account_name']}.documents.azure.com:443/",
                "function_app_url": f"https://{function_config['app_name']}.azurewebsites.net"
            }
        }
        
        # Save deployment info
        with open('deployment_info.json', 'w') as f:
            json.dump(deployment_info, f, indent=2)
        
        logging.info("Deployment completed successfully")
        return deployment_info

def create_deployment_config():
    """
    Create a sample deployment configuration.
    """
    config = {
        "project_name": "billing-optimization",
        "resource_group": "billing-optimization-rg",
        "location": "East US",
        "subscription_id": "your-subscription-id-here"
    }
    
    with open('deployment_config.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    return config

def main():
    """
    Main deployment function.
    """
    # Create sample config if it doesn't exist
    if not os.path.exists('deployment_config.json'):
        config = create_deployment_config()
        print("Created deployment_config.json. Please update with your Azure subscription details.")
        return
    
    # Load configuration
    with open('deployment_config.json', 'r') as f:
        config = json.load(f)
    
    # Deploy solution
    deployment_manager = AzureDeploymentManager(config)
    result = deployment_manager.deploy_solution()
    
    if result:
        print("Deployment completed successfully!")
        print(f"Deployment info saved to deployment_info.json")
    else:
        print("Deployment failed. Check logs for details.")

if __name__ == "__main__":
    main()

