from typing import Optional
from redis import Redis
from rq import Queue

# Fallback default local connection
REDIS_URL = "redis://localhost:6379/0"
_redis_conn: Optional[Redis] = None
_incoming_queue: Optional[Queue] = None
_outgoing_queue: Optional[Queue] = None
_scheduled_queue: Optional[Queue] = None

def _init_redis(url: str = REDIS_URL) -> None:
    global _redis_conn, _incoming_queue, _outgoing_queue, _scheduled_queue
    if not _redis_conn or _redis_conn.connection_pool.connection_kwargs.get('host') not in url:
        _redis_conn = Redis.from_url(url)
        _incoming_queue = Queue("incoming_messages", connection=_redis_conn)
        _outgoing_queue = Queue("outgoing_messages", connection=_redis_conn)
        _scheduled_queue = Queue("scheduled_tasks", connection=_redis_conn)

def get_redis() -> Redis:
    """Returns the active Redis connection."""
    if not _redis_conn:
        _init_redis()
    return _redis_conn

def get_incoming_queue() -> Queue:
    """Returns the RQ queue for incoming events to be processed by Agents."""
    if not _incoming_queue:
        _init_redis()
    return _incoming_queue

def get_outgoing_queue() -> Queue:
    """Returns the RQ queue for outbound messages to be dispatched to platforms."""
    if not _outgoing_queue:
        _init_redis()
    return _outgoing_queue

def get_scheduled_queue() -> Queue:
    """Returns the RQ queue for time-based tasks like Reminders."""
    if not _scheduled_queue:
        _init_redis()
    return _scheduled_queue
