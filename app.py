from flask import Flask, jsonify, request
from pymongo import MongoClient

app = Flask(__name__)

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")  # Replace with your MongoDB connection string
db = client.mydatabase  # Replace 'mydatabase' with your database name
collection = db.mycollection  # Replace 'mycollection' with your collection name

@app.route("/")
def home():
    return "Welcome to the Flask-MongoDB App!"

# Example: Insert a document into the collection
@app.route("/add", methods=["POST"])
def add_data():
    data = request.json
    collection.insert_one(data)
    return jsonify({"message": "Data inserted successfully!"}), 201

# Example: Retrieve all documents
@app.route("/get", methods=["GET"])
def get_data():
    data = list(collection.find({}, {"_id": 0}))  # Exclude MongoDB's default `_id` field
    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True)
