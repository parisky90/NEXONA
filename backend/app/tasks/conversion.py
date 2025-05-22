import os
import tempfile
import subprocess
from celery import shared_task
from app import db, s3_service_instance
from app.models import Candidate
from flask import current_app
import uuid
import io
import datetime  # <<< === ΠΡΟΣΘΗΚΗ ΑΥΤΟΥ ΤΟΥ IMPORT ===


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def convert_docx_to_pdf_task(self, candidate_id_str: str, original_s3_key: str, original_filename: str):
    current_app.logger.info(
        f"[CV_CONVERT_TASK_START] Candidate ID: {candidate_id_str}, S3 Key: {original_s3_key}, Filename: {original_filename}. Attempt: {self.request.retries + 1}")

    try:
        candidate_uuid_obj = uuid.UUID(candidate_id_str)
    except ValueError:
        current_app.logger.error(f"[CV_CONVERT_TASK_FAIL] Invalid UUID format for candidate_id: {candidate_id_str}")
        return f"Invalid candidate_id format: {candidate_id_str}. Conversion aborted."

    candidate = db.session.get(Candidate, candidate_uuid_obj)
    if not candidate:
        current_app.logger.error(
            f"[CV_CONVERT_TASK_FAIL] Candidate with id {candidate_id_str} not found (re-fetched in task).")
        return f"Candidate {candidate_id_str} not found. Conversion aborted."

    if candidate.cv_storage_path != original_s3_key:
        if not candidate.email.startswith("placeholder-"):
            current_app.logger.warning(f"[CV_CONVERT_TASK_SKIP_UPDATE] Candidate {candidate_id_str} (merged) "
                                       f"has cv_storage_path '{candidate.cv_storage_path}' which differs from "
                                       f"task's original_s3_key '{original_s3_key}'. PDF will be generated but not linked by this task instance.")
        else:
            current_app.logger.error(
                f"[CV_CONVERT_TASK_FAIL] Mismatch: Task called with original_s3_key '{original_s3_key}' "
                f"but placeholder candidate {candidate_id_str} has cv_storage_path '{candidate.cv_storage_path}'. Aborting.")
            return f"S3 key mismatch for placeholder candidate {candidate_id_str}. Conversion aborted."

    with tempfile.TemporaryDirectory() as temp_dir:
        safe_original_filename = "".join(c if c.isalnum() or c in ('.', '_', '-') else '_' for c in original_filename)
        local_docx_path = os.path.join(temp_dir, safe_original_filename)

        try:
            current_app.logger.debug(f"[CV_CONVERT_TASK] Downloading {original_s3_key} to {local_docx_path}")
            file_bytes_content = s3_service_instance.get_file_bytes(original_s3_key)

            if not file_bytes_content:
                current_app.logger.error(
                    f"[CV_CONVERT_TASK_FAIL] Failed to download DOCX {original_s3_key} from S3 for candidate {candidate_id_str}. get_file_bytes returned None.")
                raise Exception(f"S3 Download failed (get_file_bytes returned None) for {original_s3_key}")

            with open(local_docx_path, 'wb') as f:
                f.write(file_bytes_content)
            current_app.logger.info(f"[CV_CONVERT_TASK] DOCX {original_s3_key} downloaded to {local_docx_path}")
        except AttributeError as ae:
            current_app.logger.critical(
                f"[CV_CONVERT_TASK_CRITICAL_FAIL] AttributeError: {ae}. Ensure 'get_file_bytes' method exists on S3Service instance.",
                exc_info=True)
            return f"Configuration error: S3Service object method error for candidate {candidate_id_str}."
        except Exception as download_exc:
            current_app.logger.error(
                f"[CV_CONVERT_TASK_RETRY] Error downloading DOCX {original_s3_key}: {download_exc}", exc_info=True)
            raise self.retry(exc=download_exc)

        pdf_filename_base = os.path.splitext(safe_original_filename)[0]
        output_pdf_filename_for_s3 = pdf_filename_base + '.pdf'

        cmd = [
            'libreoffice',
            '--headless',
            '--convert-to', 'pdf',
            '--outdir', temp_dir,
            local_docx_path
        ]

        current_app.logger.info(f"[CV_CONVERT_TASK] Executing LibreOffice command: {' '.join(cmd)}")

        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate(timeout=180)

            if process.returncode != 0:
                error_message = f"LibreOffice conversion failed for {local_docx_path}. RC: {process.returncode}\nStdout: {stdout.decode(errors='ignore')}\nStderr: {stderr.decode(errors='ignore')}"
                current_app.logger.error(f"[CV_CONVERT_TASK_FAIL_NO_RETRY] {error_message}")
                candidate_for_history = db.session.get(Candidate, candidate_uuid_obj)
                if candidate_for_history:
                    candidate_for_history.add_history_event(
                        event_type="CV_CONVERSION_FAILED",
                        description=f"Automated conversion of CV '{original_filename}' to PDF failed (LibreOffice error).",
                        details={"s3_key": original_s3_key, "error": stderr.decode(errors='ignore')[:500]}
                    )
                    db.session.commit()
                return f"LibreOffice conversion failed for {candidate_id_str}."

            expected_libreoffice_output_filename = os.path.splitext(os.path.basename(local_docx_path))[0] + '.pdf'
            actual_local_pdf_path = os.path.join(temp_dir, expected_libreoffice_output_filename)

            if not os.path.exists(actual_local_pdf_path):
                current_app.logger.error(
                    f"[CV_CONVERT_TASK_FAIL_NO_RETRY] Converted PDF {actual_local_pdf_path} not found. Files in dir: {os.listdir(temp_dir)}")
                candidate_for_history = db.session.get(Candidate, candidate_uuid_obj)
                if candidate_for_history:
                    candidate_for_history.add_history_event(
                        event_type="CV_CONVERSION_FAILED",
                        description=f"Automated conversion of CV '{original_filename}' to PDF failed (output file not found).",
                        details={"s3_key": original_s3_key, "expected_path": actual_local_pdf_path,
                                 "temp_dir_contents": os.listdir(temp_dir)}
                    )
                    db.session.commit()
                return f"Converted PDF not found for {candidate_id_str}."

            current_app.logger.info(f"[CV_CONVERT_TASK] DOCX successfully converted to PDF: {actual_local_pdf_path}")

        except subprocess.TimeoutExpired:
            current_app.logger.error(
                f"[CV_CONVERT_TASK_RETRY] LibreOffice conversion timed out for {original_s3_key} (Candidate: {candidate_id_str})")
            raise self.retry(exc=subprocess.TimeoutExpired(cmd, 180))
        except Exception as libre_exc:
            current_app.logger.error(
                f"[CV_CONVERT_TASK_RETRY] LibreOffice command execution error for {original_s3_key}: {libre_exc}",
                exc_info=True)
            raise self.retry(exc=libre_exc)

        pdf_s3_key_to_upload = f"resumes_pdf/{candidate.candidate_id}/{output_pdf_filename_for_s3}"

        current_app.logger.debug(
            f"[CV_CONVERT_TASK] Uploading PDF from {actual_local_pdf_path} to S3 key {pdf_s3_key_to_upload}")
        try:
            with open(actual_local_pdf_path, 'rb') as pdf_file_obj_to_upload:
                uploaded_pdf_s3_key_returned = s3_service_instance.upload_file_obj(
                    file_obj_content_bytes=pdf_file_obj_to_upload.read(),
                    object_name=pdf_s3_key_to_upload,
                    ContentType='application/pdf'
                )

            if not uploaded_pdf_s3_key_returned:
                current_app.logger.error(
                    f"[CV_CONVERT_TASK_FAIL] Failed to upload PDF {pdf_s3_key_to_upload} to S3 for candidate {candidate_id_str}. Upload function returned None.")
                raise Exception(f"S3 PDF Upload failed for {pdf_s3_key_to_upload}")

            current_app.logger.info(f"[CV_CONVERT_TASK] PDF {uploaded_pdf_s3_key_returned} uploaded to S3.")
        except AttributeError as ae:
            current_app.logger.critical(
                f"[CV_CONVERT_TASK_CRITICAL_FAIL] AttributeError during S3 upload: {ae}. Ensure 'upload_file_obj' method exists on S3Service instance.",
                exc_info=True)
            return f"Configuration error: S3Service object method error for S3 upload (candidate {candidate_id_str})."
        except Exception as upload_pdf_exc:
            current_app.logger.error(
                f"[CV_CONVERT_TASK_RETRY] Error uploading PDF to S3 for {candidate_id_str}: {upload_pdf_exc}",
                exc_info=True)
            raise self.retry(exc=upload_pdf_exc)

        try:
            candidate_to_update_pdf_key = db.session.get(Candidate, candidate_uuid_obj)
            if not candidate_to_update_pdf_key:
                current_app.logger.warning(
                    f"[CV_CONVERT_TASK] Candidate {candidate_id_str} no longer found in DB before PDF key update (possibly merged and deleted). PDF for original key {original_s3_key} is at {uploaded_pdf_s3_key_returned}, but not linked.")
                return f"Candidate {candidate_id_str} (placeholder) not found for PDF key update. PDF generated: {uploaded_pdf_s3_key_returned}"

            if candidate_to_update_pdf_key.cv_storage_path == original_s3_key:
                candidate_to_update_pdf_key.cv_pdf_storage_key = uploaded_pdf_s3_key_returned
                candidate_to_update_pdf_key.add_history_event(
                    event_type="CV_CONVERTED_TO_PDF",
                    description=f"CV '{original_filename}' successfully converted to PDF.",
                    details={"original_s3_key": original_s3_key, "pdf_s3_key": uploaded_pdf_s3_key_returned}
                )
                # Χρήση του datetime module που κάναμε import
                candidate_to_update_pdf_key.updated_at = datetime.datetime.now(datetime.timezone.utc)
                db.session.commit()
                current_app.logger.info(
                    f"[CV_CONVERT_TASK_SUCCESS] Candidate {candidate_id_str} updated with cv_pdf_storage_key: {uploaded_pdf_s3_key_returned}")
            else:
                current_app.logger.info(
                    f"[CV_CONVERT_TASK_INFO] PDF generated for {original_s3_key} (candidate {candidate_id_str}), "
                    f"but candidate's current cv_storage_path is {candidate_to_update_pdf_key.cv_storage_path}. "
                    f"PDF key {uploaded_pdf_s3_key_returned} not set on this candidate record by this task instance. "
                    f"This should be handled by the parsing task if a merge occurred.")

            return f"Successfully converted CV for S3 key {original_s3_key}. PDF S3 key: {uploaded_pdf_s3_key_returned}"
        except Exception as db_exc:
            current_app.logger.error(
                f"[CV_CONVERT_TASK_RETRY] DB Error updating candidate {candidate_id_str} with PDF key: {db_exc}",
                exc_info=True)
            db.session.rollback()
            raise self.retry(exc=db_exc)