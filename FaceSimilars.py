import uuid
import face_recognition
from sklearn.metrics.pairwise import cosine_similarity
from PIL import Image
import os
from concurrent.futures import ProcessPoolExecutor
from sqlighter import DataBase
from ObjectStorage import ObjectStorage


def process_image(unknown_encoding, current_row, category, margin):
    object_storage = ObjectStorage()
    try:
        image = object_storage.get_img(str(current_row[2]), category)
        if image is None:
            return None

        face_encodings = face_recognition.face_encodings(image)
        face_locations = face_recognition.face_locations(image)
        for encoding, face_location in zip(face_encodings, face_locations):
            similarity = cosine_similarity([unknown_encoding], [encoding])[0][0]

            if similarity > 0.7:
                return similarity, current_row[2], face_location, current_row[1]
    except Exception as e:
        print(f"Ошибка при обработке изображения {current_row[2]}: {e}")
    return None


def find_most_similar_face(category, image_file_uploaded):
    db_service = DataBase()
    object_storage = ObjectStorage()
    actor_photos = 'actor_photos'

    if not os.path.exists(actor_photos):
        os.makedirs(actor_photos)

    try:
        unknown_image = face_recognition.load_image_file(image_file_uploaded)
        unknown_encoding = face_recognition.face_encodings(unknown_image)[0]

        margin = 100
        ids = db_service.get_all_ids(category)

        max_similarity = -1
        most_similar_data = None

        with ProcessPoolExecutor(max_workers=4) as executor:
            results = [
                executor.submit(process_image, unknown_encoding, db_service.get_by_id(category, id), category, margin) for
                id in ids]

            for future in results:
                result = future.result()
                if result and result[0] > max_similarity:
                    max_similarity = result[0]
                    most_similar_data = result

        if most_similar_data:
            _, most_similar_file, most_similar_face_location, most_similar_actor_name = most_similar_data
            image = object_storage.get_img(most_similar_file, category)
            top, right, bottom, left = most_similar_face_location

            top = max(0, top - margin)
            right = min(image.shape[1], right + margin)
            bottom = min(image.shape[0], bottom + margin)
            left = max(0, left - margin)

            face_image = image[top:bottom, left:right]
            pil_image = Image.fromarray(face_image)
            unique_filename = str(uuid.uuid4()) + ".jpg"
            cropped_filename = os.path.join(actor_photos, unique_filename)
            pil_image.save(cropped_filename)
            return [cropped_filename, most_similar_actor_name]
        else:
            return None
    except Exception as e:
        print(f"Ошибка: {e}")
        return None
