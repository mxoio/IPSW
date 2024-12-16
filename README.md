Automate iPhone/iPad Update Downloads

This script is designed to automate the download of iPhone and iPad updates. It is especially useful in scenarios where updating devices over slow or unreliable Wi-Fi can be time-consuming. By using this script, you can download updates over a faster network (depending on where the script is running) and schedule the process to run overnight, avoiding interruptions during the workday.

Setting Up Email Notifications

To enable email notifications for completed updates, this script uses a Google email account. You will need to generate an app-specific password from your Google account to allow the script to send emails.

Steps to Generate a Google App Password:
Go to your Google Account Management page.
Navigate to Security.
Use the search bar to locate App Passwords.
Generate an app password and enter it in the script configuration.
Configuration Instructions

Here are the specific lines of code you need to edit to customize the script for your environment:

Lines 19-20: Adjust the logging configuration. Set the directory path where logs will be saved.
Lines 201-203: Update your Google account email, the recipient email address, and the app password for sending notifications.
Lines 214-215: Provide the URL for the GUI of your directory to view the progress or completion status of the downloads.
Line 239: Location of where your IPSW downloads will be stored.
Log Viewer Script

This project includes an optional secondary script called log_viewer, which provides a web-based GUI to monitor the download progress. To configure this script:

Adjust the script to match the directory where your logs are saved (e.g., detailed_logging.log and download_progress.log).
It is recommended to keep the log file names the same for consistency.
The log viewer script offers a convenient way to visually track download progress and completed updates.

The script will automatically start downloading updates at 12:00 am each day.

Follow these steps to set up and enjoy a smoother, more efficient process for managing iPhone and iPad updates!

Let me know if this works or if you'd like further refinements!