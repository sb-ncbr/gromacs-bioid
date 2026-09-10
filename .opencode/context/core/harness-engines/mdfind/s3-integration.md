# MDFind S3 Integration Guide

## Core Concept
S3 integration patterns for downloading simulation files from MDFind storage. Includes boto3 setup, parallel downloads, and error handling.

## Key Points
- Use boto3 with presigned URLs for secure access
- Celery workers for parallel downloads (10+ concurrent)
- Retry logic with exponential backoff
- Progress tracking in database

## Boto3 Setup

```python
import boto3
from botocore.config import Config

s3_client = boto3.client(
    's3',
    endpoint_url=os.getenv('S3_ENDPOINT'),
    aws_access_key_id=os.getenv('S3_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('S3_SECRET_ACCESS_KEY'),
    config=Config(
        retries={'max_attempts': 5, 'mode': 'adaptive'},
        connect_timeout=5,
        read_timeout=300
    )
)
```

## Download Pattern

```python
def download_simulation(simulation_id: str, s3_key: str, dest_path: str):
    """Download simulation from S3 with retry logic."""
    for attempt in range(5):
        try:
            s3_client.download_file(
                Bucket=os.getenv('S3_BUCKET'),
                Key=s3_key,
                Filename=dest_path,
                Config=TransferConfig(
                    multipart_threshold=8 * 1024 * 1024,
                    multipart_chunksize=8 * 1024 * 1024,
                    max_concurrency=4
                )
            )
            return True
        except ClientError as e:
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
```

## Celery Task

```python
@app.task(bind=True, max_retries=3)
def download_simulation_task(self, sim_id: str, s3_key: str):
    try:
        dest = f"/data/simulations/{sim_id}"
        download_simulation(sim_id, s3_key, dest)
        update_db_status(sim_id, 'completed')
        return {'status': 'success', 'sim_id': sim_id}
    except Exception as exc:
        raise self.retry(exc, countdown=60)
```

## Worker Configuration

```bash
# Start 10 workers for parallel downloads
celery -A src.api.workers worker --loglevel=info --concurrency=10

# Or in Kubernetes: replicas: 10 in deployment
```

## Progress Tracking

```python
class ProgressCallback:
    def __init__(self, filename):
        self._filename = filename
        self._seen = 0
    
    def __call__(self, bytes_amount):
        self._seen += bytes_amount
        # Update database with progress
        update_download_progress(self._filename, self._seen)
```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `AccessDenied` | Wrong credentials | Check S3 secret, IAM policies |
| `NoSuchKey` | File doesn't exist | Verify MDFind index |
| `TimeoutError` | Large file, small timeout | Increase `read_timeout: 300` |
| `ConnectionError` | Network issue | Retry with backoff |

## References
- `architecture.md` - Overall architecture
- `kubernetes.md` - K8s deployment
