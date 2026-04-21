"""
Quick test script to verify Google Drive upload through the service layer.

Usage:
    cd backend
    python test_drive_upload.py
"""
import sys
import os

# Ensure the backend package is importable
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from app.services.google_drive_service import GoogleDriveService

def main():
    service = GoogleDriveService()

    if not service._enabled:
        print("ERROR: Google Drive is disabled. Check your .env for:")
        print("  GOOGLE_DRIVE_ENABLED=true")
        print("  GOOGLE_DRIVE_OAUTH_CREDENTIALS_FILE=<path>")
        print("  GOOGLE_DRIVE_FOLDER_ID=<folder-id>")
        return

    # Upload from bytes (simplest — no temp file needed)
    content = b"Hello from Trinity Platform! This is a Google Drive integration test."
    file_id = service.upload_file_from_bytes(
        file_bytes=content,
        filename="test_upload.txt",
        subfolder="test",
        content_type="text/plain",
    )

    if file_id:
        print(f"SUCCESS - file uploaded to Google Drive")
        print(f"  File ID : {file_id}")
        print(f"  Folder  : test/")
        print(f"  Name    : test_upload.txt")

        # Clean up — delete the test file
        answer = input("\nDelete the test file from Drive? [y/N]: ").strip().lower()
        if answer == "y":
            deleted = service.delete_file(file_id)
            print("Deleted." if deleted else "Delete failed.")
    else:
        print("FAILED - upload returned None. Check the logs above for details.")


if __name__ == "__main__":
    main()
