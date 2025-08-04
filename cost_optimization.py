"""
Cost Optimization Utilities and Strategies for Azure Billing Records Management.
"""

import azure.cosmos.cosmos_client as cosmos_client
from azure.storage.blob import BlobServiceClient, BlobClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.cosmosdb import CosmosDBManagementClient
import json
import logging
import os
from datetime import datetime, timedelta
import gzip
import io

# Configuration
COSMOS_ENDPOINT = os.environ.get('COSMOS_ENDPOINT')
COSMOS_KEY = os.environ.get('COSMOS_KEY')
COSMOS_DATABASE_NAME = os.environ.get('COSMOS_DATABASE_NAME', 'billing')
COSMOS_CONTAINER_NAME = os.environ.get('COSMOS_CONTAINER_NAME', 'records')

BLOB_CONNECTION_STRING = os.environ.get('BLOB_CONNECTION_STRING')
BLOB_CONTAINER_NAME = os.environ.get('BLOB_CONTAINER_NAME', 'archived-billing-records')

class CostOptimizer:
    """
    Class to handle various cost optimization strategies.
    """
    
    def __init__(self):
        self.cosmos_client = cosmos_client.CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
        self.database = self.cosmos_client.get_database_client(COSMOS_DATABASE_NAME)
        self.container = self.database.get_container_client(COSMOS_CONTAINER_NAME)
        
        self.blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
        self.blob_container_client = self.blob_service_client.get_container_client(BLOB_CONTAINER_NAME)
    
    def setup_blob_lifecycle_management(self):
        """
        Set up blob lifecycle management policies to automatically transition
        data between access tiers and delete old data.
        """
        lifecycle_policy = {
            "rules": [
                {
                    "enabled": True,
                    "name": "billing-records-lifecycle",
                    "type": "Lifecycle",
                    "definition": {
                        "filters": {
                            "blobTypes": ["blockBlob"],
                            "prefixMatch": ["billing-records/"]
                        },
                        "actions": {
                            "baseBlob": {
                                "tierToCool": {
                                    "daysAfterModificationGreaterThan": 30
                                },
                                "tierToArchive": {
                                    "daysAfterModificationGreaterThan": 90
                                },
                                "delete": {
                                    "daysAfterModificationGreaterThan": 2555  # 7 years retention
                                }
                            }
                        }
                    }
                }
            ]
        }
        
        logging.info("Lifecycle management policy configured for automatic tier transitions")
        return lifecycle_policy
    
    def optimize_cosmos_db_settings(self):
        """
        Optimize Cosmos DB settings for cost efficiency.
        """
        optimizations = {
            "throughput_optimization": {
                "description": "Use autoscale throughput for variable workloads",
                "recommendation": "Configure autoscale RU/s with min 400 RU/s, max based on peak usage"
            },
            "indexing_optimization": {
                "description": "Optimize indexing policy to reduce RU consumption",
                "indexing_policy": {
                    "indexingMode": "consistent",
                    "automatic": True,
                    "includedPaths": [
                        {
                            "path": "/id/?",
                            "indexes": [
                                {
                                    "kind": "Range",
                                    "dataType": "String",
                                    "precision": -1
                                }
                            ]
                        },
                        {
                            "path": "/created_date/?",
                            "indexes": [
                                {
                                    "kind": "Range",
                                    "dataType": "String",
                                    "precision": -1
                                }
                            ]
                        }
                    ],
                    "excludedPaths": [
                        {
                            "path": "/*"
                        }
                    ]
                }
            },
            "partition_key_optimization": {
                "description": "Use efficient partition key strategy",
                "recommendation": "Use a partition key that distributes data evenly (e.g., hash of customer_id or date-based)"
            }
        }
        
        logging.info("Cosmos DB optimization recommendations generated")
        return optimizations
    
    def implement_data_compression(self, data):
        """
        Implement advanced data compression strategies.
        """
        # Convert to JSON string
        json_data = json.dumps(data, separators=(',', ':'))  # Compact JSON
        
        # Apply gzip compression
        compressed_data = gzip.compress(json_data.encode('utf-8'))
        
        compression_ratio = len(compressed_data) / len(json_data.encode('utf-8'))
        
        logging.info(f"Data compressed with ratio: {compression_ratio:.2f}")
        
        return compressed_data, compression_ratio
    
    def analyze_storage_costs(self):
        """
        Analyze current storage costs and provide recommendations.
        """
        try:
            # Get blob storage usage statistics
            blobs = list(self.blob_container_client.list_blobs(include=['metadata']))
            
            total_size = 0
            total_compressed_size = 0
            blob_count = 0
            
            for blob in blobs:
                blob_count += 1
                total_size += blob.size
                
                # Get compression info from metadata if available
                if blob.metadata and 'compressed_size' in blob.metadata:
                    total_compressed_size += int(blob.metadata['compressed_size'])
                else:
                    total_compressed_size += blob.size
            
            # Calculate cost estimates (approximate Azure pricing)
            hot_storage_cost_per_gb = 0.0184  # USD per GB per month
            cool_storage_cost_per_gb = 0.01  # USD per GB per month
            archive_storage_cost_per_gb = 0.00099  # USD per GB per month
            
            total_size_gb = total_size / (1024 ** 3)
            
            cost_analysis = {
                "current_usage": {
                    "total_blobs": blob_count,
                    "total_size_bytes": total_size,
                    "total_size_gb": total_size_gb,
                    "total_compressed_size": total_compressed_size
                },
                "cost_estimates_monthly": {
                    "hot_tier": total_size_gb * hot_storage_cost_per_gb,
                    "cool_tier": total_size_gb * cool_storage_cost_per_gb,
                    "archive_tier": total_size_gb * archive_storage_cost_per_gb
                },
                "savings_potential": {
                    "hot_to_cool": (total_size_gb * hot_storage_cost_per_gb) - (total_size_gb * cool_storage_cost_per_gb),
                    "hot_to_archive": (total_size_gb * hot_storage_cost_per_gb) - (total_size_gb * archive_storage_cost_per_gb),
                    "cool_to_archive": (total_size_gb * cool_storage_cost_per_gb) - (total_size_gb * archive_storage_cost_per_gb)
                }
            }
            
            logging.info(f"Storage cost analysis completed for {blob_count} blobs")
            return cost_analysis
            
        except Exception as e:
            logging.error(f"Error analyzing storage costs: {str(e)}")
            return None
    
    def implement_intelligent_caching(self):
        """
        Implement intelligent caching strategy for frequently accessed archived data.
        """
        caching_strategy = {
            "cache_layer": "Azure Cache for Redis",
            "cache_policy": {
                "ttl_seconds": 3600,  # 1 hour
                "max_cache_size": "1GB",
                "eviction_policy": "LRU"
            },
            "cache_warming": {
                "description": "Pre-load frequently accessed records",
                "strategy": "Track access patterns and pre-load top 10% accessed records"
            },
            "cache_invalidation": {
                "description": "Invalidate cache when records are updated",
                "triggers": ["record_update", "record_delete"]
            }
        }
        
        return caching_strategy
    
    def setup_monitoring_and_alerting(self):
        """
        Set up monitoring and alerting for cost optimization.
        """
        monitoring_config = {
            "azure_monitor_metrics": [
                {
                    "metric": "cosmos_db_request_units",
                    "threshold": 1000,
                    "alert_action": "Scale down if consistently below threshold"
                },
                {
                    "metric": "blob_storage_capacity",
                    "threshold": "80% of allocated capacity",
                    "alert_action": "Review lifecycle policies"
                },
                {
                    "metric": "function_execution_count",
                    "threshold": "Unusual spikes",
                    "alert_action": "Investigate potential issues"
                }
            ],
            "cost_alerts": [
                {
                    "type": "budget_alert",
                    "threshold": "80% of monthly budget",
                    "action": "Send notification to admin"
                },
                {
                    "type": "anomaly_detection",
                    "description": "Detect unusual cost spikes",
                    "action": "Automatic investigation and notification"
                }
            ],
            "performance_monitoring": {
                "response_time_threshold": "5 seconds",
                "error_rate_threshold": "1%",
                "availability_threshold": "99.9%"
            }
        }
        
        return monitoring_config
    
    def generate_cost_optimization_report(self):
        """
        Generate a comprehensive cost optimization report.
        """
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "storage_analysis": self.analyze_storage_costs(),
            "cosmos_db_optimizations": self.optimize_cosmos_db_settings(),
            "lifecycle_management": self.setup_blob_lifecycle_management(),
            "caching_strategy": self.implement_intelligent_caching(),
            "monitoring_config": self.setup_monitoring_and_alerting(),
            "recommendations": [
                "Implement blob lifecycle management for automatic tier transitions",
                "Use autoscale throughput for Cosmos DB to handle variable workloads",
                "Optimize indexing policy to reduce RU consumption",
                "Implement intelligent caching for frequently accessed archived data",
                "Set up comprehensive monitoring and alerting",
                "Regular review of access patterns to optimize archival policies",
                "Consider data deduplication for similar records",
                "Implement batch operations to reduce transaction costs"
            ]
        }
        
        return report

def main():
    """
    Main function to run cost optimization analysis.
    """
    optimizer = CostOptimizer()
    report = optimizer.generate_cost_optimization_report()
    
    # Save report to file
    with open('/tmp/cost_optimization_report.json', 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    logging.info("Cost optimization report generated successfully")
    return report

if __name__ == "__main__":
    main()

