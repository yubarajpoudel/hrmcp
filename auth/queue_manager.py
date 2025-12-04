from rq import Queue, Worker
from redis import Redis

class QueueManager:
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client
        self.queue = Queue(connection=self.redis_client)
    
    def enqueue(self, func, *args, **kwargs):
        job = self.queue.enqueue(func, *args, **kwargs)
        return {
            "job_id": job.id,
            "job_status": job.get_status(),
            "message": "Job enqueued successfully"
        }
    def get_job_status(self, job_id):
        job = self.queue.fetch_job(job_id)
        return {
            "job_id": job.id,
            "job_status": job.get_status()
        }

    def start_worker(self):
        """Start an RQ worker for the default queue.
        This replaces the separate worker.py script.
        """
        worker = Worker([self.queue], connection=self.redis_client)
        print("Starting RQ worker...")
        print("Listening on queue: default")
        worker.work()
