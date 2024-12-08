from flask import Flask, jsonify, request
from pymongo import MongoClient


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
import logging
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
    """
    Retrieve all shift data.
    """
    data = list(metrics_collection.find({}, {"_id": 0}))
    return jsonify(data)

# READ: Retrieve shift data by date and shift
@app.route("/get/<string:date>/<int:day_shift>", methods=["GET"])
def get_data_by_shift(date, day_shift):
    """
    Retrieve shift data for a specific date and shift.
    """
    data = metrics_collection.find_one({"date": date, "day-shift": day_shift}, {"_id": 0})
    if not data:
        return jsonify({"error": "No data found for the given date and shift"}), 404
    return jsonify(data)

# READ: Retrieve daily max metrics
@app.route("/get-daily-max/<string:date>", methods=["GET"])
def get_daily_max(date):
    """
    Retrieve the maximum CPU and memory usage for a given date.
    """

    max_metrics = daily_max_collection.find_one({"date": date}, {"_id": 0})
    if not max_metrics:
        return jsonify({"error": f"No max metrics found for the given date: {date}"}), 404
    return jsonify(max_metrics)


# UPDATE: Update a shift document
@app.route("/update/<string:date>/<int:day_shift>", methods=["PUT"])
def update_shift_data(date, day_shift):
    """
    Update a shift document by date and day-shift.
    """
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
    """
    Delete a shift document by date and day-shift.
    """
    result = metrics_collection.delete_one({"date": date, "day-shift": day_shift})
    if result.deleted_count == 0:
        return jsonify({"error": "No data found to delete for the given date and shift"}), 404
    return jsonify({"message": "Data deleted successfully!"})

if __name__ == "__main__":
    app.run(debug=True)
