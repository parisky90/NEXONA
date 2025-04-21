# backend/app/services/s3_service.py

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from flask import current_app
import logging
import io # For BytesIO stream

# Configure basic logging for the service
# Note: Flask's app logger might be preferred if configured globally
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _get_s3_client():
    """Helper function to create and return an S3 client using config."""
    # Attempt to get credentials and region from Flask app config
    aws_access_key_id = current_app.config.get('AWS_ACCESS_KEY_ID')
    aws_secret_access_key = current_app.config.get('AWS_SECRET_ACCESS_KEY')
    region_name = current_app.config.get('S3_REGION')

    # Check if explicit credentials are fully provided
    if aws_access_key_id and aws_secret_access_key and region_name:
        logger.info("Attempting S3 client creation using configured credentials.")
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=region_name
            )
            # Optional: Add a check here, e.g., s3_client.list_buckets() but requires ListAllMyBuckets permission
            logger.info("S3 client created successfully using configured credentials.")
            return s3_client
        except Exception as e:
            logger.error(f"Failed to create S3 client with explicit credentials: {e}", exc_info=True)
            return None
    else:
        # If explicit credentials aren't fully set, try relying on implicit credentials (e.g., IAM role, ~/.aws/credentials)
        logger.warning("AWS credentials or region not fully configured in app config. Attempting implicit credentials.")
        try:
            # Boto3 searches standard locations if no explicit creds are passed
            s3_client = boto3.client('s3', region_name=region_name) # Still need region if not implicit
             # Optional check here too
            logger.info("S3 client created successfully using implicit credentials/region configuration.")
            return s3_client
        except NoCredentialsError:
             logger.error("No AWS credentials found (checked environment, config files, IAM role). Cannot create S3 client.")
             return None
        except Exception as e:
             logger.error(f"Failed to create S3 client with implicit credentials: {e}", exc_info=True)
             return None


def upload_file(file_obj, object_name):
    """
    Upload a file-like object to an S3 bucket.

    :param file_obj: File-like object to upload (e.g., request.files['cv_file']).
                     Must support read() and seek().
    :param object_name: S3 object name (key). If None, returns False.
    :return: object_name if file was uploaded, else None.
    """
    if object_name is None:
        logger.error("No S3 object name provided for upload.")
        return None

    s3_client = _get_s3_client()
    if not s3_client:
        logger.error("S3 client unavailable, cannot upload file.")
        return None # Error logged in _get_s3_client

    bucket_name = current_app.config.get('S3_BUCKET')
    if not bucket_name:
        logger.error("S3_BUCKET configuration is missing.")
        return None

    try:
        # Ensure file stream is at the beginning before upload
        file_obj.seek(0)
        # upload_fileobj handles multipart uploads for larger files automatically
        s3_client.upload_fileobj(
            file_obj,
            bucket_name,
            object_name
            # Optional: Add ExtraArgs for things like ACL, ContentType, etc.
            # Example: Determine content type dynamically if needed
            # content_type = getattr(file_obj, 'content_type', 'application/octet-stream')
            # ExtraArgs={'ACL': 'private', 'ContentType': content_type}
        )
        logger.info(f"Successfully uploaded {object_name} to bucket {bucket_name}.")
        return object_name # Return the key on success
    except ClientError as e:
        logger.error(f"S3 ClientError during upload of {object_name}: {e}", exc_info=True)
        return None
    except NoCredentialsError:
        # This might be caught by _get_s3_client already, but as a safeguard
        logger.error("AWS credentials not available for S3 upload.")
        return None
    except Exception as e:
         logger.error(f"An unexpected error occurred during S3 upload of {object_name}: {e}", exc_info=True)
         return None


def delete_file(object_name):
    """
    Delete an object from an S3 bucket.

    :param object_name: S3 object name (key) to delete.
    :return: True if deletion API call was successful, False otherwise.
             Note: S3 deletion might have eventual consistency.
    """
    if not object_name:
        logger.warning("No S3 object name provided for deletion.")
        return False

    s3_client = _get_s3_client()
    if not s3_client:
        logger.error("S3 client unavailable, cannot delete file.")
        return False

    bucket_name = current_app.config.get('S3_BUCKET')
    if not bucket_name:
        logger.error("S3_BUCKET configuration is missing.")
        return False

    try:
        s3_client.delete_object(Bucket=bucket_name, Key=object_name)
        logger.info(f"Successfully initiated deletion of {object_name} from bucket {bucket_name}.")
        return True
    except ClientError as e:
        logger.error(f"S3 ClientError during deletion of {object_name}: {e}", exc_info=True)
        return False
    except Exception as e:
         logger.error(f"An unexpected error occurred during S3 deletion of {object_name}: {e}", exc_info=True)
         return False


def generate_presigned_url(object_name, expiration=3600):
    """
    Generate a presigned URL to share an S3 object for temporary GET access.

    :param object_name: S3 object name (key).
    :param expiration: Time in seconds for the presigned URL to remain valid (default: 1 hour).
    :return: Presigned URL as string if successful, else None.
    """
    if not object_name:
        logger.warning("No S3 object name provided for generating presigned URL.")
        return None

    s3_client = _get_s3_client()
    if not s3_client:
        logger.error("S3 client unavailable, cannot generate presigned URL.")
        return None

    bucket_name = current_app.config.get('S3_BUCKET')
    if not bucket_name:
        logger.error("S3_BUCKET configuration is missing.")
        return None

    try:
        # Generate URL for GET request
        response = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_name},
            ExpiresIn=expiration
            # HttpMethod='GET' # GET is default
        )
        logger.info(f"Generated presigned URL for {object_name} expiring in {expiration} seconds.")
        return response
    except ClientError as e:
        logger.error(f"S3 ClientError generating presigned URL for {object_name}: {e}", exc_info=True)
        return None
    except Exception as e:
         logger.error(f"An unexpected error occurred generating presigned URL for {object_name}: {e}", exc_info=True)
         return None


def get_file_bytes(object_name):
    """
    Downloads a file's content from S3 as bytes.

    :param object_name: S3 object name (key).
    :return: File content as bytes if successful, else None.
    """
    if not object_name:
        logger.warning("No S3 object name provided for download.")
        return None

    s3_client = _get_s3_client()
    if not s3_client:
        logger.error("S3 client unavailable, cannot download file bytes.")
        return None

    bucket_name = current_app.config.get('S3_BUCKET')
    if not bucket_name:
        logger.error("S3_BUCKET configuration is missing.")
        return None

    try:
        # Use a BytesIO buffer to download the file object's content into memory
        file_byte_stream = io.BytesIO()
        s3_client.download_fileobj(Bucket=bucket_name, Key=object_name, Fileobj=file_byte_stream)
        # Reset stream position to the beginning before reading its content
        file_byte_stream.seek(0)
        # Read the entire content as bytes
        file_bytes = file_byte_stream.read()
        logger.info(f"Successfully downloaded bytes for {object_name} from S3.")
        return file_bytes
    except ClientError as e:
        # Handle specific errors like the object not existing
        if e.response['Error']['Code'] == '404' or 'NoSuchKey' in str(e): # Check common indicators for not found
            logger.error(f"S3 Error: Object {object_name} not found in bucket {bucket_name}.")
        else:
            logger.error(f"S3 ClientError during download of {object_name}: {e}", exc_info=True)
        return None
    except Exception as e:
         logger.error(f"An unexpected error occurred during S3 download of {object_name}: {e}", exc_info=True)
         return None