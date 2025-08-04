"""
Azure Functions App configuration for billing records archival and retrieval.
"""

import azure.functions as func
import logging
from archival_function import main as archival_main
from retrieval_function import main as retrieval_main, batch_retrieve

# Configure logging
logging.basicConfig(level=logging.INFO)

app = func.FunctionApp()

@app.timer_trigger(schedule="0 0 2 * * *", arg_name="mytimer", run_on_startup=False,
              use_monitor=False) 
def archival_timer(mytimer: func.TimerRequest) -> None:
    """
    Timer trigger for archival function - runs daily at 2 AM UTC.
    """
    if mytimer.past_due:
        logging.info('The timer is past due!')
    
    archival_main(mytimer)

@app.route(route="retrieve", methods=["GET", "POST"])
def retrieve_record(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP trigger for retrieving individual billing records.
    """
    return retrieval_main(req)

@app.route(route="retrieve/batch", methods=["POST"])
def retrieve_batch_records(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP trigger for batch retrieval of billing records.
    """
    return batch_retrieve(req)

