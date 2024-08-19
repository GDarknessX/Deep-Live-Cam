from typing import Any, List
import cv2
import insightface
import threading

import modules.globals
import modules.processors.frame.core
from modules.core import update_status
from modules.face_analyser import get_one_face, get_many_faces, get_one_face_left, get_one_face_right
from modules.typing import Face, Frame
from modules.utilities import conditional_download, resolve_relative_path, is_image, is_video

FACE_SWAPPER = None
THREAD_LOCK = threading.Lock()
NAME = 'DLC.FACE-SWAPPER'


def pre_check() -> bool:
    download_directory_path = resolve_relative_path('../models')
    conditional_download(download_directory_path, ['https://huggingface.co/hacksider/deep-live-cam/blob/main/inswapper_128_fp16.onnx'])
    return True


def pre_start() -> bool:
    if not is_image(modules.globals.source_path):
        update_status('Select an image for source path.', NAME)
        return False
    elif not get_one_face(cv2.imread(modules.globals.source_path)):
        update_status('No face in source path detected.', NAME)
        return False
    if not is_image(modules.globals.target_path) and not is_video(modules.globals.target_path):
        update_status('Select an image or video for target path.', NAME)
        return False
    return True


def get_face_swapper() -> Any:
    global FACE_SWAPPER

    with THREAD_LOCK:
        if FACE_SWAPPER is None:
            model_path = resolve_relative_path('../models/inswapper_128_fp16.onnx')
            FACE_SWAPPER = insightface.model_zoo.get_model(model_path, providers=modules.globals.execution_providers)
    return FACE_SWAPPER


def swap_face(source_face: Face, target_face: Face, temp_frame: Frame) -> Frame:
    return get_face_swapper().get(temp_frame, target_face, source_face, paste_back=True)


def process_frame(source_face: List[Face], temp_frame: Frame) -> Frame:
    if modules.globals.many_faces:
        many_faces = get_many_faces(temp_frame)
        if many_faces:
            for target_face in many_faces:
                if modules.globals.flip_faces:
                    temp_frame = swap_face(source_face[1], target_face, temp_frame)
                else:
                    temp_frame = swap_face(source_face[0], target_face, temp_frame)
    else:
        target_faces = get_two_faces(temp_frame)
        # Check if more then one target face is found
        if len(target_faces) >= 2:
            # Swap both target faces when with source image. Works best when source image 
            # has two faces. If source image has one face then one face is used for both 
            # target faces 
            if modules.globals.both_faces:
                # Flip source faces left to right
                if modules.globals.flip_faces:
                    # Swap right source face with left target face
                    temp_frame = swap_face(source_face[1], target_faces[0], temp_frame)
                    # Swap left source face with right target face
                    temp_frame = swap_face(source_face[0], target_faces[1], temp_frame)
                else:
                    # Swap left source face with left target face
                    temp_frame = swap_face(source_face[0], target_faces[0], temp_frame)
                    # Swap right source face with right target face
                    temp_frame = swap_face(source_face[1], target_faces[1], temp_frame)
            
            # When we have two target faces we can replace left or right face
            # Swap one face with left target face or right target face
            elif modules.globals.detect_face_right:
                # Swap left source face with right target face
                if modules.globals.flip_faces:
                    # Swap right source face with right target face
                    temp_frame = swap_face(source_face[1], target_faces[1], temp_frame)
                else:
                    # Swap left source face with right target face
                    temp_frame = swap_face(source_face[0], target_faces[1], temp_frame)

            else:
                # Swap left source face with left target face
                if modules.globals.flip_faces:
                    # Swap left source face with left target face
                    temp_frame = swap_face(source_face[1], target_faces[0], temp_frame)
                else:
                    # Swap right source face with left target face
                    temp_frame = swap_face(source_face[0], target_faces[0], temp_frame)

        elif len(target_faces) == 1:
            # If only one target face is found, swap with the first source face
            # Swap left source face with left target face
            if modules.globals.flip_faces:
                # Swap left source face with left target face
                temp_frame = swap_face(source_face[1], target_faces[0], temp_frame)
            else:
                # Swap right source face with left target face
                temp_frame = swap_face(source_face[0], target_faces[0], temp_frame)

    return temp_frame


def process_frames(source_path: str, temp_frame_paths: List[str], progress: Any = None) -> None:
    
    source_image_left = None  # Initialize variable for the selected face image
    source_image_right = None  # Initialize variable for the selected face image

    if source_image_left is None and source_path:
        source_image_left = get_one_face_left(cv2.imread(source_path))
    if source_image_right is None and source_path:
        source_image_right = get_one_face_right(cv2.imread(source_path))


    for temp_frame_path in temp_frame_paths:
        temp_frame = cv2.imread(temp_frame_path)
        try:
            result = process_frame([source_image_left,source_image_right], temp_frame)
            cv2.imwrite(temp_frame_path, result)
        except Exception as exception:
            print(exception)
            pass
        if progress:
            progress.update(1)


def process_image(source_path: str, target_path: str, output_path: str) -> None:
    
    source_image_left = None  # Initialize variable for the selected face image
    source_image_right = None  # Initialize variable for the selected face image

    if source_image_left is None and source_path:
        source_image_left = get_one_face_left(cv2.imread(source_path))
    if source_image_right is None and source_path:
        source_image_right = get_one_face_right(cv2.imread(source_path))

    source_face = get_one_face(cv2.imread(source_path))
    target_frame = cv2.imread(target_path)
    result = process_frame([source_image_left,source_image_right], target_frame)
    cv2.imwrite(output_path, result)


def process_video(source_path: str, temp_frame_paths: List[str]) -> None:
    modules.processors.frame.core.process_video(source_path, temp_frame_paths, process_frames)

def get_two_faces(frame: Frame) -> List[Face]:
    faces = get_many_faces(frame)
    if faces:
        # Sort faces from left to right based on the x-coordinate of the bounding box
        sorted_faces = sorted(faces, key=lambda x: x.bbox[0])
        return sorted_faces[:2]  # Return up to two faces, leftmost and rightmost
    return []