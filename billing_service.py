"""
Main Billing Service that maintains API compatibility while routing requests
to appropriate storage (Cosmos DB for hot data, Blob Storage for archived data).
"""

import azure.cosmos.cosmos_client as cosmos_client
from azure.storage.blob import BlobServiceClient
import json
import logging
import os
import gzip
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import requests

# Configuration
COSMOS_ENDPOINT = os.environ.get('COSMOS_ENDPOINT')
COSMOS_KEY = os.environ.get('COSMOS_KEY')
COSMOS_DATABASE_NAME = os.environ.get('COSMOS_DATABASE_NAME', 'billing')
COSMOS_CONTAINER_NAME = os.environ.get('COSMOS_CONTAINER_NAME', 'records')

BLOB_CONNECTION_STRING = os.environ.get('BLOB_CONNECTION_STRING')
BLOB_CONTAINER_NAME = os.environ.get('BLOB_CONTAINER_NAME', 'archived-billing-records')

RETRIEVAL_FUNCTION_URL = os.environ.get('RETRIEVAL_FUNCTION_URL')

app = Flask(__name__)

# Initialize clients
cosmos_client_instance = cosmos_client.CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
database = cosmos_client_instance.get_database_client(COSMOS_DATABASE_NAME)
container = database.get_container_client(COSMOS_CONTAINER_NAME)

blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
blob_container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)

@app.route('/billing/records', methods=['POST'])
def create_billing_record():
    """
    Create a new billing record in Cosmos DB.
    """
    try:
        record_data = request.get_json()
        
        if not record_data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        # Add metadata
        record_data['created_date'] = datetime.utcnow().isoformat()
        record_data['updated_date'] = datetime.utcnow().isoformat()
        
        # Ensure ID exists
        if 'id' not in record_data:
            record_data['id'] = str(uuid.uuid4())
        
        # Create record in Cosmos DB
        created_record = container.create_item(body=record_data)
        
        logging.info(f'Created billing record: {created_record["id"]}')
        
        return jsonify(created_record), 201
        
    except Exception as e:
        logging.error(f'Error creating billing record: {str(e)}')
        return jsonify({"error": "Internal server error"}), 500

@app.route('/billing/records/<record_id>', methods=['GET'])
def get_billing_record(record_id):
    """
    Retrieve a billing record by ID. Checks both hot and archived storage.
    """
    try:
        # First, try to get from Cosmos DB (hot data)
        record = get_from_cosmos_db(record_id)
        
        if record:
            logging.info(f'Record {record_id} found in Cosmos DB')
            return jsonify(record), 200
        
        # If not found in Cosmos DB, try archived storage
        logging.info(f'Record {record_id} not found in Cosmos DB, checking archived storage')
        
        if RETRIEVAL_FUNCTION_URL:
            # Use Azure Function for retrieval
            response = requests.get(f'{RETRIEVAL_FUNCTION_URL}?id={record_id}')
            if response.status_code == 200:
                return jsonify(response.json()), 200
            elif response.status_code == 404:
                return jsonify({"error": "Record not found"}), 404
        else:
            # Direct blob storage access
            archived_record = get_from_blob_storage(record_id)
            if archived_record:
                logging.info(f'Record {record_id} found in archived storage')
                return jsonify(archived_record), 200
        
        # Record not found anywhere
        logging.warning(f'Record {record_id} not found')
        return jsonify({"error": "Record not found"}), 404
        
    except Exception as e:
        logging.error(f'Error retrieving billing record: {str(e)}')
        return jsonify({"error": "Internal server error"}), 500

@app.route('/billing/records/<record_id>', methods=['PUT'])
def update_billing_record(record_id):
    """
    Update a billing record. Only works for records in Cosmos DB (hot data).
    """
    try:
        update_data = request.get_json()
        
        if not update_data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        # Check if record exists in Cosmos DB
        existing_record = get_from_cosmos_db(record_id)
        
        if not existing_record:
            return jsonify({"error": "Record not found or is archived (updates not allowed for archived records)"}), 404
        
        # Update the record
        existing_record.update(update_data)
        existing_record['updated_date'] = datetime.utcnow().isoformat()
        
        updated_record = container.replace_item(item=existing_record, body=existing_record)
        
        logging.info(f'Updated billing record: {record_id}')
        
        return jsonify(updated_record), 200
        
    except Exception as e:
        logging.error(f'Error updating billing record: {str(e)}')
        return jsonify({"error": "Internal server error"}), 500

@app.route('/billing/records/<record_id>', methods=['DELETE'])
def delete_billing_record(record_id):
    """
    Delete a billing record. Only works for records in Cosmos DB (hot data).
    """
    try:
        # Check if record exists in Cosmos DB
        existing_record = get_from_cosmos_db(record_id)
        
        if not existing_record:
            return jsonify({"error": "Record not found or is archived (deletion not allowed for archived records)"}), 404
        
        # Delete the record
        container.delete_item(item=record_id, partition_key=record_id)
        
        logging.info(f'Deleted billing record: {record_id}')
        
        return jsonify({"message": "Record deleted successfully"}), 200
        
    except Exception as e:
        logging.error(f'Error deleting billing record: {str(e)}')
        return jsonify({"error": "Internal server error"}), 500

@app.route('/billing/records', methods=['GET'])
def list_billing_records():
    """
    List billing records with pagination. Only returns records from Cosmos DB (hot data).
    """
    try:
        # Get query parameters
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        # Query Cosmos DB
        query = "SELECT * FROM c ORDER BY c.created_date DESC"
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        
        # Apply pagination
        paginated_items = items[offset:offset + limit]
        
        result = {
            "records": paginated_items,
            "total": len(items),
            "limit": limit,
            "offset": offset
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f'Error listing billing records: {str(e)}')
        return jsonify({"error": "Internal server error"}), 500

@app.route('/billing/records/batch', methods=['POST'])
def batch_get_billing_records():
    """
    Retrieve multiple billing records by IDs.
    """
    try:
        request_data = request.get_json()
        
        if not request_data or 'ids' not in request_data:
            return jsonify({"error": "Record IDs list is required"}), 400
        
        record_ids = request_data['ids']
        if not isinstance(record_ids, list):
            return jsonify({"error": "Record IDs must be a list"}), 400
        
        results = {}
        
        for record_id in record_ids:
            # Try Cosmos DB first
            record = get_from_cosmos_db(record_id)
            
            if not record:
                # Try archived storage
                if RETRIEVAL_FUNCTION_URL:
                    try:
                        response = requests.get(f'{RETRIEVAL_FUNCTION_URL}?id={record_id}')
                        if response.status_code == 200:
                            record = response.json()
                    except Exception:
                        pass
                else:
                    record = get_from_blob_storage(record_id)
            
            if record:
                results[record_id] = record
            else:
                results[record_id] = {"error": "Record not found"}
        
        return jsonify(results), 200
        
    except Exception as e:
        logging.error(f'Error in batch retrieval: {str(e)}')
        return jsonify({"error": "Internal server error"}), 500

def get_from_cosmos_db(record_id):
    """
    Retrieve a record from Cosmos DB.
    """
    try:
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

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint.
    """
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

