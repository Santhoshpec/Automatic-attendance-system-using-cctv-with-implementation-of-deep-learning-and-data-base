from flask import Flask, request, jsonify
import cv2
import face_recognition
import numpy as np
import mysql.connector
from datetime import datetime

app = Flask(__name__)

# Connect to MySQL
def connect_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="santhosh"
    )

@app.route("/start_recognition", methods=["POST"])
def start_recognition():
    video_capture = cv2.VideoCapture(0)
    known_face_encodings = []
    known_face_names = []

    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("SELECT si.student_id, s.name, si.image_path FROM student_images si JOIN students s ON si.student_id = s.id")
    student_images = cursor.fetchall()

    for _, name, image_path in student_images:
        image = face_recognition.load_image_file(image_path)
        encoding = face_recognition.face_encodings(image)[0]
        known_face_encodings.append(encoding)
        known_face_names.append(name)

    ret, frame = video_capture.read()
    if not ret:
        return jsonify({"error": "Camera error"})

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_frame)
    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

    for face_encoding in face_encodings:
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
        name = "Unknown"

        if True in matches:
            match_index = matches.index(True)
            name = known_face_names[match_index]
            cursor.execute("INSERT INTO attendance (name, entry_time) VALUES (%s, %s)", (name, datetime.now()))
            connection.commit()

    video_capture.release()
    return jsonify({"message": "Face recognized!", "name": name})

if __name__ == "__main__":
    app.run(debug=True)
