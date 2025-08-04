"""
Azure Function for retrieving archived billing records from Blob Storage.
This function is triggered by HTTP requests when archived data is needed.
"""

import azure.functions as func
import azure.cosmos.cosmos_client as cosmos_client
from azure.storage.blob import BlobServiceClient
import json
import logging
import os
import gzip
from datetime import datetime

# Configuration
COSMOS_ENDPOINT = os.environ.get('COSMOS_ENDPOINT')
COSMOS_KEY = os.environ.get('COSMOS_KEY')
COSMOS_DATABASE_NAME = os.environ.get('COSMOS_DATABASE_NAME', 'billing')
COSMOS_CONTAINER_NAME = os.environ.get('COSMOS_CONTAINER_NAME', 'records')

BLOB_CONNECTION_STRING = os.environ.get('BLOB_CONNECTION_STRING')
BLOB_CONTAINER_NAME = os.environ.get('BLOB_CONTAINER_NAME', 'archived-billing-records')

def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Main function to handle HTTP requests for retrieving billing records.
    """
    logging.info('Processing billing record retrieval request')
    
    try:
        # Get record ID from request
        record_id = req.params.get('id')
        if not record_id:
            try:
                req_body = req.get_json()
                record_id = req_body.get('id') if req_body else None
            except ValueError:
                pass
        
        if not record_id:
            return func.HttpResponse(
                json.dumps({"error": "Record ID is required"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # First, try to get the record from Cosmos DB (hot data)
        record = get_from_cosmos_db(record_id)
        
        if record:
            logging.info(f'Record {record_id} found in Cosmos DB')
            return func.HttpResponse(
                json.dumps(record, default=str),
                status_code=200,
                mimetype="application/json"
            )
        
        # If not found in Cosmos DB, try archived storage
        logging.info(f'Record {record_id} not found in Cosmos DB, checking archived storage')
        archived_record = get_from_blob_storage(record_id)
        
        if archived_record:
            logging.info(f'Record {record_id} found in archived storage')
            return func.HttpResponse(
                json.dumps(archived_record, default=str),
                status_code=200,
                mimetype="application/json"
            )
        
        # Record not found anywhere
        logging.warning(f'Record {record_id} not found in either Cosmos DB or archived storage')
        return func.HttpResponse(
            json.dumps({"error": "Record not found"}),
            status_code=404,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f'Error retrieving record: {str(e)}')
        return func.HttpResponse(
            json.dumps({"error": "Internal server error"}),
            status_code=500,
            mimetype="application/json"
        )

def get_from_cosmos_db(record_id):
    """
    Retrieve a record from Cosmos DB.
    """
    try:
        cosmos_client_instance = cosmos_client.CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
        database = cosmos_client_instance.get_database_client(COSMOS_DATABASE_NAME)
        container = database.get_container_client(COSMOS_CONTAINER_NAME)
        
        # Try to read the item directly
        try:
            item = container.read_item(item=record_id, partition_key=record_id)
            return item
        except Exception:
            # If direct read fails, try querying
            query = f"SELECT * FROM c WHERE c.id = '{record_id}'"
            items = list(container.query_items(query=query, enable_cross_partition_query=True))
            return items[0] if items else None
            
    except Exception as e:
        logging.error(f'Error retrieving from Cosmos DB: {str(e)}')
        return None

def get_from_blob_storage(record_id):
    """
    Retrieve a record from Blob Storage.
    """
    try:
        blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
        blob_container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)
        
        # Construct blob name
        blob_name = f"billing-records/{record_id}.json.gz"
        
        # Download and decompress the blob
        blob_client = blob_container_client.get_blob_client(blob_name)
        
        if not blob_client.exists():
            return None
        
        # Download the compressed data
        compressed_data = blob_client.download_blob().readall()
        
        # Decompress and parse JSON
        decompressed_data = gzip.decompress(compressed_data)
        record = json.loads(decompressed_data.decode('utf-8'))
        
        # Add metadata about retrieval
        record['_retrieved_from_archive'] = True
        record['_retrieval_timestamp'] = datetime.utcnow().isoformat()
        
        return record
        
    except Exception as e:
        logging.error(f'Error retrieving from Blob Storage: {str(e)}')
        return None

def batch_retrieve(req: func.HttpRequest) -> func.HttpResponse:
    """
    Function to handle batch retrieval of multiple records.
    """
    logging.info('Processing batch billing record retrieval request')
    
    try:
        req_body = req.get_json()
        if not req_body or 'ids' not in req_body:
            return func.HttpResponse(
                json.dumps({"error": "Record IDs list is required"}),
                status_code=400,
                mimetype="application/json"
            )
        
        record_ids = req_body['ids']
        if not isinstance(record_ids, list):
            return func.HttpResponse(
                json.dumps({"error": "Record IDs must be a list"}),
                status_code=400,
                mimetype="application/json"
            )
        
        results = {}
        
        for record_id in record_ids:
            # Try Cosmos DB first
            record = get_from_cosmos_db(record_id)
            
            if not record:
                # Try archived storage
                record = get_from_blob_storage(record_id)
            
            if record:
                results[record_id] = record
            else:
                results[record_id] = {"error": "Record not found"}
        
        return func.HttpResponse(
            json.dumps(results, default=str),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f'Error in batch retrieval: {str(e)}')
        return func.HttpResponse(
            json.dumps({"error": "Internal server error"}),
            status_code=500,
            mimetype="application/json"
        )

