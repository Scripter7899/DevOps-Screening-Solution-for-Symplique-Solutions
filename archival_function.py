"""
Azure Function for archiving old billing records from Cosmos DB to Blob Storage.
This function runs on a schedule to identify and migrate records older than 3 months.
"""

import azure.functions as func
import azure.cosmos.cosmos_client as cosmos_client
from azure.storage.blob import BlobServiceClient
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

ARCHIVE_THRESHOLD_MONTHS = int(os.environ.get('ARCHIVE_THRESHOLD_MONTHS', '3'))
BATCH_SIZE = int(os.environ.get('BATCH_SIZE', '100'))

def main(mytimer: func.TimerRequest) -> None:
    """
    Main function triggered by timer to archive old billing records.
    """
    logging.info('Starting billing records archival process')
    
    try:
        # Initialize clients
        cosmos_client_instance = cosmos_client.CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
        database = cosmos_client_instance.get_database_client(COSMOS_DATABASE_NAME)
        container = database.get_container_client(COSMOS_CONTAINER_NAME)
        
        blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
        blob_container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)
        
        # Ensure blob container exists
        try:
            blob_container_client.create_container()
        except Exception:
            pass  # Container might already exist
        
        # Calculate cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=ARCHIVE_THRESHOLD_MONTHS * 30)
        cutoff_timestamp = cutoff_date.isoformat()
        
        logging.info(f'Archiving records older than {cutoff_timestamp}')
        
        # Query for old records
        query = f"SELECT * FROM c WHERE c.created_date < '{cutoff_timestamp}'"
        
        archived_count = 0
        failed_count = 0
        
        # Process records in batches
        for items in query_items_in_batches(container, query, BATCH_SIZE):
            batch_results = process_batch(items, blob_container_client, container)
            archived_count += batch_results['archived']
            failed_count += batch_results['failed']
        
        logging.info(f'Archival process completed. Archived: {archived_count}, Failed: {failed_count}')
        
    except Exception as e:
        logging.error(f'Error in archival process: {str(e)}')
        raise

def query_items_in_batches(container, query, batch_size):
    """
    Query items from Cosmos DB in batches to manage memory usage.
    """
    items = list(container.query_items(query=query, enable_cross_partition_query=True))
    
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]

def process_batch(items, blob_container_client, cosmos_container):
    """
    Process a batch of items for archival.
    """
    archived_count = 0
    failed_count = 0
    
    for item in items:
        try:
            # Archive the record
            if archive_record(item, blob_container_client):
                # Delete from Cosmos DB after successful archival
                cosmos_container.delete_item(item=item['id'], partition_key=item.get('partition_key', item['id']))
                archived_count += 1
                logging.info(f'Successfully archived and deleted record: {item["id"]}')
            else:
                failed_count += 1
                logging.warning(f'Failed to archive record: {item["id"]}')
                
        except Exception as e:
            failed_count += 1
            logging.error(f'Error processing record {item.get("id", "unknown")}: {str(e)}')
    
    return {'archived': archived_count, 'failed': failed_count}

def archive_record(record, blob_container_client):
    """
    Archive a single record to blob storage with compression.
    """
    try:
        # Generate blob name based on record ID and date
        blob_name = f"billing-records/{record['id']}.json.gz"
        
        # Compress the record data
        record_json = json.dumps(record, default=str)
        compressed_data = gzip.compress(record_json.encode('utf-8'))
        
        # Upload to blob storage
        blob_container_client.upload_blob(
            name=blob_name,
            data=compressed_data,
            overwrite=True,
            metadata={
                'record_id': record['id'],
                'archived_date': datetime.utcnow().isoformat(),
                'original_size': str(len(record_json)),
                'compressed_size': str(len(compressed_data))
            }
        )
        
        return True
        
    except Exception as e:
        logging.error(f'Error archiving record {record.get("id", "unknown")}: {str(e)}')
        return False

