# backend/app/services/s3_service.py

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from flask import current_app
import logging
import io  # For BytesIO stream


class S3Service:
    def __init__(self, app=None):
        """
        Initializes the S3Service.
        If an app instance is provided, it uses its config.
        The S3 client is initialized when first needed or via init_app.
        """
        self.s3_client = None
        self.bucket_name = None
        self.logger = logging.getLogger(__name__)  # Default logger
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """
        Initialize S3 client and settings with Flask app configuration.
        This method allows for initializing the service in an app factory pattern.
        """
        self.logger = app.logger if hasattr(app, 'logger') else logging.getLogger(__name__)
        self.bucket_name = app.config.get('S3_BUCKET')
        if not self.bucket_name:
            self.logger.error("S3_BUCKET configuration is missing. S3Service will not be functional.")
            # Consider raising an error if S3 is critical: raise ValueError("S3_BUCKET not configured")
            return

        # Client initialization is deferred to _get_client to ensure app context is available
        # if this instance was created outside of an app context initially.
        # However, we can attempt to pre-initialize if an app is provided here.
        self._initialize_client_from_config(app.config)

    def _initialize_client_from_config(self, app_config):
        """Helper to initialize s3_client from app_config."""
        aws_access_key_id = app_config.get('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = app_config.get('AWS_SECRET_ACCESS_KEY')
        region_name = app_config.get('S3_REGION')
        s3_endpoint_url = app_config.get('S3_ENDPOINT_URL')  # For MinIO or other S3-compatible

        client_config_args = {}
        if region_name:
            client_config_args['region_name'] = region_name
        if s3_endpoint_url:
            client_config_args['endpoint_url'] = s3_endpoint_url
            # For MinIO, you might need to adjust signature version if not using v4 by default
            # from botocore.client import Config as BotoConfig
            # client_config_args['config'] = BotoConfig(signature_version='s3v4')

        try:
            if aws_access_key_id and aws_secret_access_key:
                self.logger.info(
                    f"Attempting S3 client creation using configured credentials (region: {region_name}, endpoint: {s3_endpoint_url}).")
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key,
                    **client_config_args
                )
            else:
                self.logger.warning(
                    f"AWS access key/secret not fully configured. Attempting implicit credentials (region: {region_name}, endpoint: {s3_endpoint_url}).")
                self.s3_client = boto3.client('s3', **client_config_args)

            # Optional: Test connection (e.g., self.s3_client.list_buckets())
            # This requires appropriate permissions.
            self.logger.info("S3 client appears to be configured.")
        except NoCredentialsError:
            self.logger.error("No AWS credentials found. S3Service will not be functional.")
            self.s3_client = None  # Ensure client is None
        except ClientError as e:
            self.logger.error(f"Failed to create S3 client due to ClientError: {e}", exc_info=True)
            self.s3_client = None
        except Exception as e:
            self.logger.error(f"An unexpected error occurred creating S3 client: {e}", exc_info=True)
            self.s3_client = None

        if not self.s3_client:
            self.logger.error("S3 client could not be initialized. S3 operations will fail.")

    def _get_client(self):
        """
        Returns the S3 client. Initializes it if not already done and app context is available.
        This ensures that the client is created with the correct app configuration.
        """
        if not self.s3_client:
            if current_app:  # Check if we are in an app context
                self.logger.info("S3 client not initialized. Attempting re-initialization with current_app.")
                self.init_app(current_app._get_current_object())  # Use the actual app object
            else:
                self.logger.error("S3 client not initialized and no Flask app context available.")
                # raise RuntimeError("S3 client cannot be initialized outside of a Flask app context or without prior init_app call.")
                return None  # Or handle more gracefully

        if not self.s3_client:  # Check again after attempting init_app
            self.logger.error("S3 client is still not available after attempting initialization.")
            return None

        return self.s3_client

    def upload_file_obj(self, file_obj_content_bytes, object_name, ContentType='application/octet-stream',
                        ACL='private'):
        """
        Upload a file's content (bytes) to an S3 bucket.
        :param file_obj_content_bytes: Bytes of the file to upload.
        :param object_name: S3 object name (key).
        :param ContentType: The content type of the file.
        :param ACL: The ACL for the uploaded object.
        :return: object_name if file was uploaded, else None.
        """
        client = self._get_client()
        if not client or not self.bucket_name:
            self.logger.error("S3 client or bucket name not available for upload_file_obj.")
            return None
        if object_name is None:
            self.logger.error("No S3 object name provided for upload.")
            return None

        try:
            file_stream = io.BytesIO(file_obj_content_bytes)
            client.upload_fileobj(
                file_stream,
                self.bucket_name,
                object_name,
                ExtraArgs={'ContentType': ContentType, 'ACL': ACL}
            )
            self.logger.info(f"Successfully uploaded {object_name} to bucket {self.bucket_name}.")
            return object_name
        except ClientError as e:
            self.logger.error(f"S3 ClientError during upload of {object_name}: {e}", exc_info=True)
            return None
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during S3 upload of {object_name}: {e}", exc_info=True)
            return None

    def delete_file(self, object_name):
        """Delete an object from an S3 bucket."""
        client = self._get_client()
        if not client or not self.bucket_name:
            self.logger.error("S3 client or bucket name not available for delete_file.")
            return False
        if not object_name:
            self.logger.warning("No S3 object name provided for deletion.")
            return False
        try:
            client.delete_object(Bucket=self.bucket_name, Key=object_name)
            self.logger.info(f"Successfully initiated deletion of {object_name} from bucket {self.bucket_name}.")
            return True
        except ClientError as e:
            self.logger.error(f"S3 ClientError during deletion of {object_name}: {e}", exc_info=True)
            return False
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during S3 deletion of {object_name}: {e}", exc_info=True)
            return False

    def create_presigned_url(self, object_name, expiration=3600):
        """Generate a presigned URL to share an S3 object."""
        client = self._get_client()
        if not client or not self.bucket_name:
            self.logger.error("S3 client or bucket name not available for create_presigned_url.")
            return None
        if not object_name:
            self.logger.warning("No S3 object name provided for generating presigned URL.")
            return None
        try:
            response = client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': object_name},
                ExpiresIn=expiration
            )
            self.logger.info(f"Generated presigned URL for {object_name} expiring in {expiration} seconds.")
            return response
        except ClientError as e:
            self.logger.error(f"S3 ClientError generating presigned URL for {object_name}: {e}", exc_info=True)
            return None
        except Exception as e:
            self.logger.error(f"An unexpected error occurred generating presigned URL for {object_name}: {e}",
                              exc_info=True)
            return None

    def get_file_bytes(self, object_name):
        """Downloads a file's content from S3 as bytes."""
        client = self._get_client()
        if not client or not self.bucket_name:
            self.logger.error("S3 client or bucket name not available for get_file_bytes.")
            return None
        if not object_name:
            self.logger.warning("No S3 object name provided for download.")
            return None
        try:
            file_byte_stream = io.BytesIO()
            client.download_fileobj(Bucket=self.bucket_name, Key=object_name, Fileobj=file_byte_stream)
            file_byte_stream.seek(0)
            file_bytes = file_byte_stream.read()
            self.logger.info(f"Successfully downloaded bytes for {object_name} from S3.")
            return file_bytes
        except ClientError as e:
            if e.response['Error']['Code'] == '404' or 'NoSuchKey' in str(e):
                self.logger.error(f"S3 Error: Object {object_name} not found in bucket {self.bucket_name}.")
            else:
                self.logger.error(f"S3 ClientError during download of {object_name}: {e}", exc_info=True)
            return None
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during S3 download of {object_name}: {e}", exc_info=True)
            return None