from auth.queue_manager import QueueManager

if __name__ == "__main__":
    queue_manager = QueueManager()
    queue_manager.start_worker()