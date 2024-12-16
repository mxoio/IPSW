from flask import Flask, render_template_string
import os
import re
from collections import defaultdict

# Define paths for different log files
DETAILED_LOG_PATH = "Location for detailed_logging.log"
PROGRESS_LOG_PATH = "Location for download_progress.log"

app = Flask(__name__)

# Enhanced HTML Template with Bootstrap
HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <link href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css" rel="stylesheet">
    <title>IPSW Downloads Log Viewer</title>
    <style>
      body { font-family: Arial, sans-serif; background-color: #f8f9fa; padding: 20px; }
      pre { background-color: #ffffff; padding: 15px; border: 1px solid #ddd; }
      a { margin-right: 15px; text-decoration: none; color: #007bff; }
      .progress { margin-top: 20px; }
      .card { margin-top: 20px; }
    </style>
  </head>
  <body>
    <div class="container">
      <h1 class="my-4">IPSW Downloads Log Viewer</h1>
      <nav class="mb-4">
        <a href="/" class="btn btn-primary">Progress Log</a>
        <a href="/detailed" class="btn btn-secondary">Detailed Log</a>
      </nav>
      {% if progress_entries %}
        {% for entry in progress_entries %}
          <div class="card mb-3">
            <div class="card-body">
              <h5 class="card-title">{{ entry.device }}</h5>
              <p class="card-text">
                Download progress: {{ entry.progress }}%<br>
                Speed: {{ entry.speed }}<br>
                Time Elapsed: {{ entry.time_elapsed }}
              </p>
              <div class="progress">
                <div class="progress-bar" role="progressbar" style="width: {{ entry.progress }}%;" aria-valuenow="{{ entry.progress }}" aria-valuemin="0" aria-valuemax="100">{{ entry.progress }}%</div>
              </div>
            </div>
          </div>
        {% endfor %}
      {% elif detailed_entries %}
        <table class="table table-bordered">
          <thead>
            <tr>
              <th>Device</th>
              <th>Action</th>
              <th>Count</th>
            </tr>
          </thead>
          <tbody>
            {% for entry in detailed_entries %}
              <tr>
                <td>{{ entry.device }}</td>
                <td>{{ entry.action }}</td>
                <td>{{ entry.count }}</td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      {% else %}
        <pre>{{ log_content }}</pre>
      {% endif %}
    </div>
  </body>
</html>
"""

@app.route('/')
def progress_log():
    progress_entries = parse_progress_log(PROGRESS_LOG_PATH)
    # Sort in-progress downloads first (progress < 100) and completed downloads last
    progress_entries = sorted(progress_entries, key=lambda x: x['progress'] == 100)
    return render_template_string(HTML_TEMPLATE, progress_entries=progress_entries)

@app.route('/detailed')
def detailed_log():
    detailed_entries = parse_detailed_log(DETAILED_LOG_PATH)
    # Sort iPhones and iPads in descending order
    detailed_entries = sorted(detailed_entries, key=lambda x: (sort_key(x['device']), x['device']), reverse=True)
    return render_template_string(HTML_TEMPLATE, detailed_entries=detailed_entries)

def read_log(log_path):
    if os.path.exists(log_path):
        with open(log_path, 'r') as log_file:
            return log_file.read()
    else:
        return "Log file not found."

def parse_progress_log(log_path):
    progress_entries = []
    if os.path.exists(log_path):
        with open(log_path, 'r') as log_file:
            for line in log_file:
                # Extended regular expression to match progress, speed, and time elapsed
                match = re.search(r'(?P<device>iPhone|iPad [\w\s]+).*? (?P<progress>\d{1,3}\.\d{2})% downloaded.*?speed: (?P<speed>[\d.]+ MB/s).*?time elapsed: (?P<time>[\d\s\w:]+)', line, re.IGNORECASE)
                if match:
                    progress_entries.append({
                        'device': match.group('device'),
                        'progress': float(match.group('progress')),
                        'speed': match.group('speed'),
                        'time_elapsed': match.group('time')
                    })
    return progress_entries

def parse_detailed_log(log_path):
    detailed_entries = defaultdict(lambda: {"count": 0, "action": ""})
    if os.path.exists(log_path):
        with open(log_path, 'r') as log_file:
            for line in log_file:
                # Regex to match lines that indicate scheduling or completion
                match = re.search(r'(Scheduling download for|Downloaded) (?P<device>.*?)(?:,|\s|\.)', line, re.IGNORECASE)
                if match:
                    action = "Scheduled" if "Scheduling download for" in line else "Completed"
                    # Normalize device names by removing any file path prefixes
                    device = match.group('device').strip()
                    device = re.sub(r'^/mnt/user/IPSW_Downloads/', '', device)  # Remove any directory prefix
                    key = (device, action)
                    detailed_entries[key]["count"] += 1
                    detailed_entries[key]["action"] = action

    # Convert defaultdict to a list for easier rendering in the template
    return [{"device": key[0], "action": value["action"], "count": value["count"]} for key, value in detailed_entries.items()]

def sort_key(device_name):
    """
    Sorts the device names in descending order based on the type of device.
    """
    if "iPhone" in device_name:
        # Extract the number from iPhone name
        match = re.search(r'iPhone\s*(\d+)', device_name, re.IGNORECASE)
        if match:
            return int(match.group(1))
    elif "iPad" in device_name:
        # Assign weights to iPad models for sorting
        if "Pro" in device_name:
            return 1000  # Ensure "iPad Pro" sorts at the top
        match = re.search(r'iPad\s*(\d+)', device_name, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return 0

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
