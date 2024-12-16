import importlib
import subprocess
import sys
import logging
import os
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import schedule
import requests
from tqdm import tqdm
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Define paths for different log files
DETAILED_LOG_PATH = "location for detailed_logging.log"
PROGRESS_LOG_PATH = "location for download_progress.log"

class ConsoleFilter(logging.Filter):
    def filter(self, record):
        return "Downloading" not in record.getMessage()

def ensure_directory_exists(path):
    if not os.path.exists(path):
        os.makedirs(path)
        logging.info(f"Created directory: {path}")
    else:
        logging.info(f"Directory already exists: {path}")

def setup_logging(log_file_path, detailed_log_path):
    ensure_directory_exists(os.path.dirname(log_file_path))  # Ensure the log directory exists
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # File handler for main log
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)

    # File handler for detailed log
    detailed_file_handler = logging.FileHandler(detailed_log_path)
    detailed_file_handler.setLevel(logging.DEBUG)
    detailed_file_handler.setFormatter(file_formatter)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(ConsoleFilter())  # Add filter to console handler

    logger.addHandler(file_handler)
    logger.addHandler(detailed_file_handler)
    logger.addHandler(console_handler)

class TqdmToLogger(tqdm):
    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(f"TqdmLogger_{kwargs.pop('device_name', 'unknown_device')}")
        self.logger.addHandler(logging.FileHandler(kwargs.pop('log_file_path', PROGRESS_LOG_PATH)))
        super().__init__(*args, **kwargs)

    def display(self, *args, **kwargs):
        pass  # Override to prevent displaying progress in console

    def write(self, msg):
        if msg.strip():  # Avoid writing empty lines
            self.logger.info(msg.strip())

def install_and_import(package):
    try:
        importlib.import_module(package)
        logging.info(f"{package} is already installed.")
    except ImportError:
        logging.info(f"{package} is not installed. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            logging.info(f"{package} has been installed.")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to install {package}. Error: {e}")

def ensure_packages(packages):
    for package in packages:
        install_and_import(package)

def get_latest_ipsw():
    global downloaded_files, download_status
    downloaded_files = []  # Reset the list at the beginning of the function
    download_status = {}  # Reset the download status

    logging.info("Starting to get the latest IPSW files...")
    try:
        response = session.get(base_url, timeout=60)
        response.raise_for_status()
        devices = response.json()
        futures = []

        # Sort the devices by release year in descending order
        sorted_devices = sorted(devices, key=lambda d: device_release_years.get(d['identifier'], 0), reverse=True)

        with ThreadPoolExecutor(max_workers=4) as executor:
            for device in sorted_devices:
                device_identifier = device['identifier']
                device_name = device['name']

                if any(device_type in device_name for device_type in device_types):
                    release_year = device_release_years.get(device_identifier, 0)
                    if release_year and release_year >= 2020:
                        firmware_url = f"https://api.ipsw.me/v4/device/{device_identifier}?type=ipsw"
                        firmware_response = session.get(firmware_url, timeout=60)
                        firmware_response.raise_for_status()
                        firmwares = firmware_response.json().get('firmwares', [])
                        if firmwares:
                            latest_firmware = sorted(firmwares, key=lambda x: x['version'], reverse=True)[0]
                            download_url = latest_firmware['url']
                            file_name = download_url.split('/')[-1]
                            file_path = os.path.join(ipsw_storage_path, file_name)
                            if not os.path.exists(file_path):
                                logging.info(f"Scheduling download for {file_name} for {device_name} ({device_identifier})...")
                                future = executor.submit(download_file, download_url, file_path, device_name)
                                futures.append(future)

        for future in as_completed(futures):
            result = future.result()
            if result:
                downloaded_files.append(result)
                if len(downloaded_files) % download_limit == 0:
                    logging.info("Pausing for a minute before starting the next batch...")
                    time.sleep(60)  # Wait for a minute before starting the next batch

        if not downloaded_files:
            message = "All downloads have been already completed. No further action required."
            logging.info(message)
        else:
            send_email_notification(downloaded_files)

    except requests.RequestException as e:
        logging.error(f"Network error occurred: {e}")
    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)

def download_file(url, file_path, device_name):
    try:
        with session.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            start_time = time.time()
            progress_update_time = start_time
            with open(file_path, 'wb') as f:
                with TqdmToLogger(total=total_size // 8192, 
                                  unit='KB', 
                                  unit_scale=True, 
                                  desc=f"Downloading {device_name}",
                                  log_file_path=PROGRESS_LOG_PATH,
                                  device_name=device_name,
                                  file=None) as t:  # No file output for tqdm
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            t.update(len(chunk) // 8192)
                            elapsed_time = time.time() - start_time
                            if time.time() - progress_update_time > 1:  # Update log every second
                                speed = f.tell() / elapsed_time / (1024 * 1024)  # Speed in MB/s
                                percentage = (f.tell() / total_size) * 100
                                downloaded_gb = f.tell() / (1024 * 1024 * 1024)
                                progress_line = (f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {device_name}: "
                                                 f"{percentage:.2f}% downloaded, {downloaded_gb:.2f} GB downloaded, "
                                                 f"download speed: {speed:.2f} MB/s, time elapsed: {convert_seconds_to_readable_time(elapsed_time)}")
                                download_status[device_name] = progress_line
                                update_progress_log()
                                progress_update_time = time.time()
            logging.info(f"Downloaded {file_path}")
            return file_path  # Return the file path to indicate success
    except requests.RequestException as e:
        logging.error(f"Failed to download file from {url} - Error: {e}")
        return None  # Return None to indicate failure
    except Exception as e:
        logging.error(f"An error occurred during download: {e}", exc_info=True)
        return None

def update_progress_log():
    with open(PROGRESS_LOG_PATH, 'w') as progress_log:
        progress_log.write('\n'.join(download_status.values()))

def convert_seconds_to_readable_time(seconds):
    if seconds == float('inf'):
        return "Unknown"
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
    elif minutes > 0:
        return f"{int(minutes)}m {int(seconds)}s"
    else:
        return f"{int(seconds)}s"

def send_email_notification(downloaded_files):
    sender_email = "youremail@here.com"
    receiver_emails = ["test1@test.com", "test2@test.com"]
    app_password = "add you app password from google here"

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = ", ".join(receiver_emails)
    message["Subject"] = "IPSW Download Notification"

    body = (
        "The following IPSW files have been downloaded:\n"
        + "\n".join(downloaded_files)
        + "\n\nTo check the downloaded updates view here for local: "
        "Add local ip here"
        "Add remotw ip here"
    )
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, app_password)
            server.sendmail(sender_email, receiver_emails, message.as_string())
        logging.info("Email notification sent successfully.")
    except Exception as e:
        logging.error(f"Failed to send email notification. Error: {e}")

def schedule_jobs():
    schedule.every().day.at("00:00").do(get_latest_ipsw)
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    setup_logging(PROGRESS_LOG_PATH, DETAILED_LOG_PATH)
    required_packages = ["requests", "tqdm", "schedule", "google-auth", "google-auth-oauthlib", "google-auth-httplib2"]
    ensure_packages(required_packages)

    ipsw_storage_path = "Downlaods storage path"
    ensure_directory_exists(ipsw_storage_path)

    download_limit = 2
    base_url = "https://api.ipsw.me/v4/devices"
    device_release_years = {
        "iPhone12,8": 2020,
        "iPhone13,2": 2020,
        "iPhone13,1": 2020,
        "iPhone13,4": 2020,
        "iPhone13,3": 2020,
        "iPhone14,2": 2021,
        "iPhone14,3": 2021,
        "iPhone14,4": 2021,
        "iPhone14,5": 2021,
        "iPhone14,6": 2022,
        "iPhone14,7": 2022,
        "iPhone14,8": 2022,
        "iPhone15,2": 2022,
        "iPhone15,3": 2022,
        "iPhone15,4": 2023,
        "iPhone15,5": 2023,
        "iPhone16,1": 2023,
        "iPhone16,2": 2023,
        "iPhone17,1": 2024,
        "iPhone17,2": 2024,
        "iPhone17,3": 2024,
        "iPhone17,4": 2024,
        "iPad8,12": 2020,
        "iPad8,9": 2020,
        "iPad8,11": 2020,
        "iPad8,10": 2020,
        "iPad13,1": 2020,
        "iPad11,6": 2020,
        "iPad11,7": 2020,
        "iPad13,2": 2020,
        "iPad13,4": 2021,
        "iPad13,5": 2021,
        "iPad13,9": 2021,
        "iPad13,11": 2021,
        "iPad13,8": 2021,
        "iPad13,10": 2021,
        "iPad13,7": 2021,
        "iPad13,6": 2021,
        "iPad12,1": 2021,
        "iPad12,2": 2021,
        "iPad14,1": 2021,
        "iPad14,2": 2021,
        "iPad13,17": 2022,
        "iPad13,16": 2022,
        "iPad13,18": 2022,
        "iPad13,19": 2022,
        "iPad14,3": 2022,
        "iPad14,4": 2022,
        "iPad14,5": 2022,
        "iPad14,6": 2022,
        "iPad16,4": 2023,
        "iPad16,3": 2023,
        "iPad14,10": 2023,
        "iPad16,5": 2023,
        "iPad16,6": 2023,
        "iPad14,11": 2023,
        "iPad14,9": 2023,
        "iPad14,8": 2023,
        "iPad16,1": 2024,
        "iPad16,2": 2024
    }

    device_types = ["iPhone", "iPad"]
    downloaded_files = []
    download_status = {}

    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))

    get_latest_ipsw()  # Manually trigger the download function for immediate feedback
    schedule_jobs()
