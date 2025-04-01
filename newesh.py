import tkinter as tk
from PIL import Image, ImageTk
import face_recognition
import numpy as np
import cv2
from datetime import datetime, timedelta
import os
import threading
import csv
import mysql.connector

class FaceRecognitionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Face Recognition Attendance System")
        self.root.geometry("800x600")

        self.known_face_encodings = []
        self.known_face_names = []
        self.entry_times = {}  # Stores when a student enters
        self.last_seen_times = {}  # Tracks last detected time
        self.exit_allowed = {}  # Controls if exit can be marked
        self.min_class_time = timedelta(minutes=5)  # Minimum required presence
        self.exit_cooldown = timedelta(minutes=2)  # Must show face after 2 mins for exit
        self.attendance_file = "attendance.csv"

        self.is_running = False  # Prevent multiple webcam starts

        self.create_widgets()
        self.load_student_data_from_db()
        self.start_webcam()

    def connect_db(self):
        """Connects to the MySQL database."""
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password="root",
            database="santhosh"
        )

    def create_widgets(self):
        self.stop_webcam_button = tk.Button(self.root, text="Stop Webcam", command=self.stop_webcam)
        self.stop_webcam_button.pack(pady=5)

        self.status_label = tk.Label(self.root, text="Status: Initializing Webcam...")
        self.status_label.pack(pady=5)

        self.image_frame = tk.Frame(self.root)
        self.image_frame.pack(fill=tk.BOTH, expand=True)

        self.image_panel = tk.Label(self.image_frame)
        self.image_panel.pack(fill=tk.BOTH, expand=True)

    def load_student_data_from_db(self):
        """Loads student face encodings from the student_images table in the database."""
        self.known_face_encodings.clear()
        self.known_face_names.clear()

        try:
            connection = self.connect_db()
            cursor = connection.cursor()

            cursor.execute("SELECT si.student_id, s.name, si.image_path FROM student_images si JOIN students s ON si.student_id = s.id")
            student_images = cursor.fetchall()

            for student_id, name, image_path in student_images:
                if os.path.exists(image_path):
                    image = face_recognition.load_image_file(image_path)
                    encodings = face_recognition.face_encodings(image)

                    if encodings:
                        for encoding in encodings:
                            self.known_face_encodings.append(encoding)
                            self.known_face_names.append(name)
                        print(f"✅ Loaded encoding for {name} from {image_path}")
                    else:
                        print(f"⚠ Warning: No face found in {image_path}, skipping...")
                else:
                    print(f"⚠ Warning: Image {image_path} not found!")

            self.status_label.config(text="Student data loaded successfully.")
        except mysql.connector.Error as error:
            print(f"❌ Database Error: {error}")
        finally:
            cursor.close()
            connection.close()

    def start_webcam(self):
        """Starts the webcam for face recognition."""
        if self.is_running:
            return  # Prevent multiple starts

        self.video_capture = cv2.VideoCapture(0)

        if not self.video_capture.isOpened():
            self.status_label.config(text="Status: Webcam failed to open.")
            self.is_running = False
            return

        self.is_running = True
        self.status_label.config(text="Status: Webcam running...")
        threading.Thread(target=self.update_frame, daemon=True).start()

    def stop_webcam(self):
        """Stops the webcam."""
        self.is_running = False
        if self.video_capture:
            self.video_capture.release()
        self.image_panel.config(image='')
        self.status_label.config(text="Status: Webcam stopped")

    def update_frame(self):
        """Continuously updates the video frame and processes face recognition."""
        while self.is_running:
            ret, frame = self.video_capture.read()
            if not ret:
                self.status_label.config(text="Status: Camera Frame Error")
                break

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame)
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            detected_names = []

            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                name = self.identify_face(face_encoding)
                detected_names.append(name)

                # Draw rectangle and label
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 255, 0), cv2.FILLED)
                cv2.putText(frame, name, (left + 6, bottom - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

                self.handle_attendance(name)

            self.check_exits(detected_names)

            # Convert frame to PIL image for display
            pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            imgtk = ImageTk.PhotoImage(image=pil_image)
            self.image_panel.imgtk = imgtk
            self.image_panel.configure(image=imgtk)

        if self.video_capture:
            self.video_capture.release()

    def identify_face(self, face_encoding):
        """Identifies a face using stored encodings."""
        face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
        best_match_index = np.argmin(face_distances) if len(face_distances) > 0 else None

        if best_match_index is not None and face_distances[best_match_index] < 0.4:
            return self.known_face_names[best_match_index]
        return "Unknown"

    def handle_attendance(self, name):
        """Marks entry attendance only if face is detected."""
        if name == "Unknown":
            return

        current_time = datetime.now()

        if name not in self.entry_times:
            self.entry_times[name] = current_time
            self.last_seen_times[name] = current_time
            self.exit_allowed[name] = False  # Reset exit permission
            print(f"✅ {name} entered at {current_time.strftime('%Y-%m-%d %H:%M:%S')}")

        elif name in self.exit_allowed and self.exit_allowed[name]:
            # Allow exit only if they show their face again
            entry_time = self.entry_times[name]
            duration = current_time - entry_time
            self.store_attendance_in_csv(name, entry_time, current_time, duration)
            print(f"✅ {name} exited at {current_time.strftime('%Y-%m-%d %H:%M:%S')} | Total Time: {duration}")

            del self.entry_times[name]
            del self.last_seen_times[name]
            del self.exit_allowed[name]

    def check_exits(self, detected_names):
        """Allows exit marking only if the student shows face again after 2 minutes."""
        current_time = datetime.now()

        for name in list(self.entry_times.keys()):
            if name not in detected_names:
                if current_time - self.last_seen_times[name] >= self.exit_cooldown:
                    self.exit_allowed[name] = True

    def store_attendance_in_csv(self, name, entry_time, exit_time, duration):
        """Saves attendance to CSV."""
        with open(self.attendance_file, mode="a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([name, entry_time.strftime("%Y-%m-%d %H:%M:%S"),
                             exit_time.strftime("%Y-%m-%d %H:%M:%S"), str(duration)])

if __name__ == "__main__":
    root = tk.Tk()
    app = FaceRecognitionApp(root)
    root.mainloop()
