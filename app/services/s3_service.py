import boto3
from botocore.config import Config # 🔥 1. THÊM DÒNG IMPORT NÀY
from botocore.exceptions import ClientError
from app.core.config import settings

def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        region_name=settings.S3_REGION_NAME,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        # 🔥 BÍ KÍP CHỐT HẠ: Phải ép nó xài Path Style cho RunPod
        config=Config(
            signature_version='s3v4',
            
        )
    )

def generate_presigned_url(key: str, expires: int = 7200): # Tăng thời gian lên 2 tiếng cho chắc
    s3_client = _get_s3_client()

    try:
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.S3_BUCKET_NAME,
                "Key": key
            },
            ExpiresIn=expires
        )
        return url

    except ClientError as exc:
        raise RuntimeError(f"Unable to generate presigned URL: {exc}")