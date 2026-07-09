import os
import pickle
from pathlib import Path

try:
    import face_recognition
except ImportError:  # pragma: no cover - optional dependency on Windows
    face_recognition = None

from config import Config


class FaceService:
    def __init__(self):
        self.dataset_dir = Path(Config.FACE_DATASET_FOLDER)
        self.dataset_dir.mkdir(parents=True, exist_ok=True)

    def save_face_encoding(self, student_id, image_path):
        if face_recognition is None:
            raise RuntimeError('face-recognition is not installed. Install it with Visual C++ build tools on Windows.')
        image = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(image)
        if not encodings:
            raise ValueError('No face detected in uploaded image')
        encoding = encodings[0]
        target_path = self.dataset_dir / f'{student_id}.pkl'
        with open(target_path, 'wb') as handle:
            pickle.dump(encoding, handle)
        return str(target_path)

    def recognize_face(self, image_path):
        if face_recognition is None:
            raise RuntimeError('face-recognition is not installed. Install it with Visual C++ build tools on Windows.')
        image = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(image)
        if not encodings:
            return None
        unknown_encoding = encodings[0]
        known_files = list(self.dataset_dir.glob('*.pkl'))
        for file_path in known_files:
            with open(file_path, 'rb') as handle:
                known_encoding = pickle.load(handle)
            distance = face_recognition.face_distance([known_encoding], unknown_encoding)[0]
            if distance < 0.45:
                return file_path.stem, float(distance)
        return None, None
