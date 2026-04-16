import time
import os
import pandas as pd
import numpy as np
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Google Cloud Storage Import
from google.cloud import storage

# --- CONFIGURATION ---
# Replace with your GCS Bucket Name (e.g., 'my-election-data-bucket')
BUCKET_NAME = "demsiasp-avev/inbox/20260602_primary/statewide"


def clean_csv_data(file_path):
    """
    Cleans shifted data while strictly preserving original column headers.
    Handles ParserErrors by dynamically identifying the widest row.
    """
    print(f"Cleaning data in {file_path}...")

    try:
        # 1. Capture original headers
        original_header_df = pd.read_csv(file_path, nrows=0, encoding="latin1")
        header_list = original_header_df.columns.tolist()

        # 2. Peek for max columns to prevent ParserError (Expected X, saw Y)
        with open(file_path, "r", encoding="latin1") as f:
            max_cols = max(len(line.split(",")) for line in f)

        # 3. Load data rows (skipping header to process raw values)
        df = pd.read_csv(
            file_path,
            names=range(max_cols),
            header=None,
            skiprows=1,
            low_memory=False,
            encoding="latin1",
        )
    except Exception as e:
        print(f"Failed to read file for cleaning: {e}")
        return file_path

    def fix_row(row):
        row_list = row.tolist()

        # AJ is Index 35. We look for a binary '1' or '0' starting from AK (36)
        # Checking up to 5 columns of potential shift (index 41)
        for i in range(36, min(len(row_list), 42)):
            val = str(row_list[i]).strip().split(".")[0]

            if val in ["0", "1"]:
                # Shift detected: Keep items 0-34 (A through AI)
                # Then take everything from index i to the end
                header_part = row_list[:35]
                data_part = row_list[i:]

                new_row = header_part + data_part

                # Pad with NaNs to match the width of the dataframe
                padding = len(row_list) - len(new_row)
                if padding > 0:
                    new_row.extend([np.nan] * padding)

                return pd.Series(new_row[: len(row_list)], index=row.index)

        return row

    # 4. Apply cleaning logic
    df = df.apply(fix_row, axis=1)

    # 5. Truncate to match original header length and re-attach headers
    df = df.iloc[:, : len(header_list)]
    df.columns = header_list

    # 6. Save cleaned version locally in /tmp
    cleaned_file_path = file_path.replace(".csv", "_cleaned.csv")
    df.to_csv(cleaned_file_path, index=False)
    return cleaned_file_path


def upload_to_bucket(file_path, destination_blob_name):
    """
    Uploads a file to a GCS bucket using Application Default Credentials (ADC).
    """
    print(f"Uploading to GCS Bucket: {BUCKET_NAME}...")
    try:
        # Implicitly uses the Service Account provided by your orchestration platform
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(destination_blob_name)

        blob.upload_from_filename(file_path)
        print(f"Upload Successful! gs://{BUCKET_NAME}/{destination_blob_name}")
    except Exception as e:
        print(f"GCS Upload Failed: {e}")


def main():
    # 1. Date and Path setup
    today_str = datetime.now().strftime("%Y-%m-%d")
    target_file_name = f"Election-{today_str}.csv"

    # Standard for orchestration: /tmp is the writable scratch space
    download_dir = (
        "/tmp"
        if os.name != "nt"
        else os.path.join(os.path.expanduser("~"), "Downloads")
    )
    full_file_path = os.path.join(download_dir, target_file_name)

    # 2. Configure Headless Chrome for Linux/Cloud workers
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu") # Extra safety for cloud workers
    chrome_options.add_argument("--remote-allow-origins=*")
    prefs = {"download.default_directory": download_dir}
    chrome_options.add_experimental_option("prefs", prefs)

    print(f"Job started for file: {target_file_name}")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # SharePoint Sharing Link (Bypasses Login Prompt)
        url = "https://sosia.sharepoint.com/:f:/s/ElectionsFileSharing/IgAb7hMCU-O5Q51fvBH20ujTAXz7ckSLGMBcoVy4Suxg-YA?e=cMK19p"
        driver.get(url)

        wait = WebDriverWait(driver, 45)

        # Locate and Select File
        file_xpath = f"//button[contains(., '{target_file_name}')] | //span[contains(., '{target_file_name}')]"
        file_element = wait.until(EC.element_to_be_clickable((By.XPATH, file_xpath)))
        file_element.click()

        # Click the Download Button in toolbar
        download_xpath = "//button[@data-automationid='downloadCommand'] | //button[@name='Download']"
        download_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, download_xpath))
        )
        download_btn.click()
        print("Download started...")

        # 3. Wait for download to finish in /tmp
        timeout = 60
        while not os.path.exists(full_file_path) and timeout > 0:
            time.sleep(1)
            timeout -= 1

        if os.path.exists(full_file_path):
            # 4. Clean Data
            cleaned_path = clean_csv_data(full_file_path)

            # 5. Upload to Bucket
            upload_to_bucket(cleaned_path, f"Cleaned_{target_file_name}")

            # 6. Delete local temp files from worker
            os.remove(full_file_path)
            if os.path.exists(cleaned_path):
                os.remove(cleaned_path)
        else:
            print(f"Error: {target_file_name} was not found or download timed out.")

    except Exception as e:
        print(f"Process failed: {e}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
