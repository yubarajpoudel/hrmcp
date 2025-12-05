from rq import Queue, Worker
from redis import Redis

from core.env.env_utils import get_settings
import redis

class QueueManager:
    def __init__(self, redis_client: Redis = None):
        settings = get_settings()
        # RQ requires raw bytes, so we need decode_responses=False
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            username=settings.REDIS_USER,
            password=settings.REDIS_PASSWORD,
            decode_responses=False
        )
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
