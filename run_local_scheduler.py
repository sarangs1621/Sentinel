import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.core.config import settings
from app.workers.tasks import dispatch_due_checks, dispatch_metric_aggregation, dispatch_pending_notifications


def main():
    print("Starting Sentinel Local Scheduler (No Redis required)...")
    print("Using eager task execution.")
    
    last_check = 0
    last_metrics = 0

    check_interval = settings.CHECK_DISPATCH_INTERVAL_SECONDS
    metrics_interval = settings.METRICS_AGGREGATION_INTERVAL_SECONDS

    while True:
        now = time.time()
        
        if now - last_check >= check_interval:
            print(f"[{time.strftime('%H:%M:%S')}] Dispatching checks and notifications...")
            try:
                dispatch_due_checks.delay()
                dispatch_pending_notifications.delay()
            except Exception as e:
                print(f"Error during dispatch: {e}")
            last_check = now
            
        if now - last_metrics >= metrics_interval:
            print(f"[{time.strftime('%H:%M:%S')}] Dispatching metrics aggregation...")
            try:
                dispatch_metric_aggregation.delay()
            except Exception as e:
                print(f"Error during metrics aggregation: {e}")
            last_metrics = now
            
        time.sleep(1)

if __name__ == "__main__":
    main()
