import mysql.connector
import os

def store_images_in_db(dataset_folder=r"C:\Users\santh\OneDrive\Desktop\main\datasets\ranjith S", store_as_blob=False):
    """Stores all image paths or binary images in MySQL."""
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="root",
            database="santhosh"
        )
        cursor = connection.cursor()

        student_name = os.path.basename(dataset_folder)  # Extract student name from folder
        cursor.execute("SELECT id FROM students WHERE name = %s", (student_name,))
        student_id = cursor.fetchone()

        if not student_id:
            print(f"⚠️ No student found with name {student_name}. Please add the student first.")
            return
        student_id = student_id[0]

        for image_name in os.listdir(dataset_folder):
            image_path = os.path.join(dataset_folder, image_name)

            if not os.path.isfile(image_path):  # Skip if not an image
                continue

            # Check if the image already exists
            cursor.execute(
                "SELECT COUNT(*) FROM student_images WHERE student_id = %s AND image_path = %s",
                (student_id, image_path),
            )
            if cursor.fetchone()[0] > 0:
                print(f"⚠️ Image {image_name} already stored. Skipping...")
                continue  # Skip duplicate entries

            if store_as_blob:
                # Read and convert image to binary
                with open(image_path, "rb") as file:
                    image_data = file.read()
                cursor.execute(
                    "INSERT INTO student_images (student_id, image_path, image_data) VALUES (%s, %s, %s)",
                    (student_id, image_path, image_data),
                )
            else:
                # Store only the image path
                cursor.execute(
                    "INSERT INTO student_images (student_id, image_path) VALUES (%s, %s)",
                    (student_id, image_path),
                )

        connection.commit()
        print("✅ Images stored in MySQL successfully!")

    except mysql.connector.Error as error:
        print(f"❌ Database Error: {error}")

    finally:
        cursor.close()
        connection.close()

# Run the function to store images
store_images_in_db(store_as_blob=False)  # Change to True if you want to store images as BLOBs
