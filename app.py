from flask import Flask, jsonify, request, send_file
from pymongo import MongoClient
from fpdf import FPDF
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import logging

app = Flask(__name__)

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")  # Replace with your MongoDB connection string
db = client.mydatabase
metrics_collection = db.system_metrics  # Collection for shift data
daily_max_collection = db.daily_max_metrics  # Collection for daily max metrics

@app.route("/")
def home():
    return "Welcome to the System Metrics API!"

# CREATE: Insert a shift document
@app.route("/add", methods=["POST"])
def add_data():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid data provided"}), 400

    # Insert data into the shift metrics collection
    metrics_collection.insert_one(data)

    # Check if all three shifts for the day are inserted
    date = data.get("date")
    shift_count = metrics_collection.count_documents({"date": date})
    if shift_count == 3:
        calculate_and_store_max_metrics(date)

    return jsonify({"message": "Data inserted successfully!"}), 201

logging.basicConfig(level=logging.DEBUG)

def calculate_and_store_max_metrics(date):
    # Fetch all documents for the given date
    shifts = list(metrics_collection.find({"date": date}))
    logging.debug(f"Shifts for {date}: {shifts}")

    if len(shifts) < 3:
        logging.error(f"Not enough shifts for {date}. Expected 3, found {len(shifts)}.")
        return

    max_cpu = {}
    max_memory = {}
    application_availability = {}

    for shift in shifts:
        cpu_usage = shift.get("cpu_usage", {})
        memory_usage = shift.get("memory_usage", {})
        app_avail = shift.get("Application_Availability", {})

        # Calculate max CPU usage
        for key, value in cpu_usage.items():
            if isinstance(value, (int, float)):  # Skip non-numeric values
                if key not in max_cpu or value > max_cpu[key]:
                    max_cpu[key] = value

        # Calculate max memory usage
        for key, value in memory_usage.items():
            if isinstance(value, (int, float)):  # Skip non-numeric values
                if key not in max_memory or value > max_memory[key]:
                    max_memory[key] = value

        # Copy Application_Availability without modification
        for key, value in app_avail.items():
            if key not in application_availability:
                application_availability[key] = value

    max_metrics = {
        "date": date,
        "max_cpu_usage": max_cpu,
        "max_memory_usage": max_memory,
        "application_availability": application_availability
    }

    # Insert max metrics into the daily_max_metrics collection
    daily_max_collection.insert_one(max_metrics)
    logging.debug(f"Inserted max metrics: {max_metrics}")

# READ: Retrieve all shift data
@app.route("/get", methods=["GET"])
def get_all_data():
    data = list(metrics_collection.find({}, {"_id": 0}))
    return jsonify(data)

# READ: Retrieve shift data by date and shift
@app.route("/get/<string:date>/<int:day_shift>", methods=["GET"])
def get_data_by_shift(date, day_shift):
    data = metrics_collection.find_one({"date": date, "day-shift": day_shift}, {"_id": 0})
    if not data:
        return jsonify({"error": "No data found for the given date and shift"}), 404
    return jsonify(data)

# READ: Retrieve daily max metrics
@app.route("/get-daily-max/<string:date>", methods=["GET"])
def get_daily_max(date):
    max_metrics = daily_max_collection.find_one({"date": date}, {"_id": 0})
    if not max_metrics:
        return jsonify({"error": f"No max metrics found for the given date: {date}"}), 404
    return jsonify(max_metrics)

# Export daily metrics as PDF
@app.route("/export-pdf/<string:date>", methods=["GET"])
def export_pdf(date):
    data = daily_max_collection.find_one({"date": date}, {"_id": 0})
    if not data:
        return jsonify({"error": "No data found for the given date"}), 404

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt=f"Daily Metrics for {date}", ln=True, align="C")
    for key, value in data.items():
        pdf.cell(200, 10, txt=f"{key}: {value}", ln=True)

    file_name = f"{date}_metrics.pdf"
    pdf.output(file_name)

    return send_file(file_name, as_attachment=True)

# Send metrics PDF via email
@app.route("/send-email/<string:date>", methods=["POST"])
def send_email(date):
    recipient_email = request.json.get("recipient_email")
    if not recipient_email:
        return jsonify({"error": "Recipient email is required"}), 400

    # Generate PDF
    pdf_path = f"{date}_metrics.pdf"
    export_pdf(date)

    # Email configuration
    sender_email = "your-email@example.com"
    sender_password = "your-email-password"
    subject = f"Daily Metrics for {date}"

    # Create email
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = recipient_email
    message["Subject"] = subject

    # Email body
    body = f"Hello team 
I hope this email finds you well,
Please find the attached report of the PTO project,
Best regards.
 {date}."
    message.attach(MIMEText(body, "plain"))

    # Attach PDF
    with open(pdf_path, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {pdf_path}",
        )
        message.attach(part)

    # Send email
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, message.as_string())

    return jsonify({"message": "Email sent successfully!"})

# UPDATE: Update a shift document
@app.route("/update/<string:date>/<int:day_shift>", methods=["PUT"])
def update_shift_data(date, day_shift):
    updated_data = request.json
    if not updated_data:
        return jsonify({"error": "Invalid data provided"}), 400
    result = metrics_collection.update_one({"date": date, "day-shift": day_shift}, {"$set": updated_data})
    if result.matched_count == 0:
        return jsonify({"error": "No data found to update for the given date and shift"}), 404
    return jsonify({"message": "Data updated successfully!"})

# DELETE: Delete a shift document
@app.route("/delete/<string:date>/<int:day_shift>", methods=["DELETE"])
def delete_shift_data(date, day_shift):
    result = metrics_collection.delete_one({"date": date, "day-shift": day_shift})
    if result.deleted_count == 0:
        return jsonify({"error": "No data found to delete for the given date and shift"}), 404
    return jsonify({"message": "Data deleted successfully!"})

if __name__ == "__main__":
    app.run(debug=True)
