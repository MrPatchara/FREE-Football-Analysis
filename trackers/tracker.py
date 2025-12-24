import logging
from typing import List, Dict, TYPE_CHECKING
import time
from datetime import datetime
import numpy as np
import pandas as pd
# Lazy import ultralytics to avoid DLL loading issues at import time
# ultralytics will be imported in Tracker.__init__ when actually needed
import supervision as sv
from utils import ellipse, triangle, ball_possession_box, get_device, get_center_of_bbox, get_foot_position, options
import os
import sys

# Type hints only - won't be evaluated at runtime
if TYPE_CHECKING:
    import ultralytics

# Get log directory path - works in both dev and PyInstaller bundle mode
if hasattr(sys, '_MEIPASS'):
    # PyInstaller bundle mode - use executable directory
    log_dir = os.path.join(os.path.dirname(sys.executable), "logs")
else:
    # Development mode - use current directory
    log_dir = "logs"

# Create logs directory if it doesn't exist
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, "tracking.log")
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

logger = logging.getLogger("tracker")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

class Tracker:
    """
    Byte tracker. 
    Tracking persons by close bounding box in next frame combined with movement and visual features like shirt colour.
    Assigning bounding boxes unique IDs.
    Predicting and then tracking with supervision instead of YOLO tracking due to overwriting goalkeepers.
    """
    def __init__(self, model_path: str, classes: List[int], verbose: bool=True, 
                 batch_size: int = None, use_half_precision: bool = True) -> None: 
        # Lazy import ultralytics to avoid DLL loading issues at module import time
        # Note: This will trigger torch import which may cause DLL loading issues
        # Try to pre-load torch DLLs to help with Windows signature validation
        
        # Pre-load torch DLLs if in PyInstaller bundle mode
        if hasattr(sys, '_MEIPASS'):
            try:
                torch_lib_path = os.path.join(sys._MEIPASS, 'torch', 'lib')
                if os.path.exists(torch_lib_path):
                    # Add to PATH
                    current_path = os.environ.get('PATH', '')
                    if torch_lib_path not in current_path:
                        os.environ['PATH'] = torch_lib_path + os.pathsep + current_path
                    # Add to DLL search path
                    try:
                        os.add_dll_directory(torch_lib_path)
                    except (OSError, AttributeError):
                        pass
            except Exception:
                pass  # Continue even if pre-loading fails
        
        try:
            if verbose:
                logger.info("Importing ultralytics (this may trigger torch import)...")
                print("Importing ultralytics...", flush=True)
            
            # Try importing torch first to validate DLLs
            try:
                import torch
                if verbose:
                    logger.info("torch imported successfully")
            except Exception as torch_error:
                if verbose:
                    logger.warning(f"torch import warning: {torch_error}")
            
            # Now import ultralytics
            import ultralytics
            if verbose:
                logger.info("ultralytics imported successfully")
        except Exception as e:
            import traceback
            error_msg = f"Failed to import ultralytics: {e}\nFull traceback:\n{traceback.format_exc()}"
            logger.error(error_msg)
            print(f"ERROR: Failed to import ultralytics: {e}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            raise ImportError(f"Could not import ultralytics. This is required for tracking. Error: {e}")
        
        self.model = ultralytics.YOLO(model_path)
        # Enable half precision for faster inference (FP16)
        if use_half_precision:
            try:
                self.model.fuse()  # Fuse model layers for faster inference
            except:
                pass  # If fusion fails, continue without it
        
        self.classes = classes
        # Optimize ByteTrack with better parameters for speed
        self.tracker = sv.ByteTrack(
            track_thresh=0.25,      # Lower threshold for initial tracking
            track_buffer=30,         # Buffer for lost tracks
            match_thresh=0.8,       # Matching threshold
            frame_rate=30            # Assumed frame rate
        )
        self.verbose = verbose
        self.interpolation_tracker = None   # used for ball annotation: don't draw ball in a large interpolation window
        self.batch_size = batch_size  # Store for use in detect_frames

    def interpolate_ball_positions(self, ball_tracks: List[Dict]) -> List[Dict]:
        """
        If the ball is not detected in every frame, take the frames where it is detected and interpolate
        ball position in the frames between by drawing a line and simulate the position evenly along the line.
        """
        # tracker_id 1 for ball, {} if nothing found, at tracker_id 1, get bbox, [] if nothing found
        # {1: {"bbox": [....]}, ...
        ball_positions = [track.get(1, {}).get("bbox", []) for track in ball_tracks]

        self.interpolation_tracker = [1 if not bbox else 0 for bbox in ball_positions]   # if no datapoint: empty list --> interpolation
        
        df_ball_positions = pd.DataFrame(ball_positions, columns=["x1", "y1", "x2", "y2"])

        df_ball_positions = df_ball_positions.interpolate() # interpolate NaN values, estimation based on previous data
        df_ball_positions = df_ball_positions.bfill()       # --> edge case beginning: no previous data --> bfill (replace NaN with next following value)

        ball_positions = [{1: {"bbox": x}} for x in df_ball_positions.to_numpy().tolist()] # transform back

        return ball_positions

    def detect_frames(self, frames: List[np.ndarray], batch_size: int=None) -> List:  # Returns List[ultralytics.engine.results.Results]
        """
        List of frame predictions processed in batches to avoid memory issues.
        Optimized for speed with adaptive batch sizing and half precision.
        """
        # Use instance batch_size if provided, otherwise use default or auto-detect
        if batch_size is None:
            batch_size = self.batch_size if self.batch_size is not None else 20
        
        # Auto-adjust batch size based on device (GPU can handle larger batches)
        device = get_device()
        if device != "cpu" and batch_size == 20:
            # Try larger batch size for GPU
            batch_size = 32
        
        detections = []
        
        start_time = time.time()

        if self.verbose:
            logger.info(f"[Device: {device}] Starting object detection at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} with batch_size={batch_size}")

        for i in range(0, len(frames), batch_size):
            frame_time = time.time()
            
            # Use half precision (FP16) for faster inference on GPU
            # conf threshold 0.15 is kept for detection, but we'll filter later
            detections_batch = self.model.predict(
                source=frames[i:i+batch_size], 
                conf=0.15, 
                verbose=False,  # Reduce verbosity for speed
                device=device,
                half=(device != "cpu"),  # Use FP16 on GPU only
                imgsz=640,  # Standard size for speed/accuracy balance
                agnostic_nms=False,  # Class-aware NMS
                max_det=300  # Limit detections for speed
            )
            detections += detections_batch

            if self.verbose:
                logger.info(f"Processed frames {i} to {min(i+batch_size-1, len(frames))} in {time.time() - frame_time:.2f} seconds.")
        
        if self.verbose:
            logger.info(f"Detected objects in {len(frames)} frames in {time.time() - start_time:.2f} seconds.")
  
        return detections

    def get_object_tracks(self, frames: List[np.ndarray]) -> Dict[str, List[Dict]]:        
        detections = self.detect_frames(frames)

        # key: tracker_id, value: bbox, index: frame
        tracks = {
            "players": [],      # {tracker_id: {"bbox": [....]}, tracker_id: {"bbox": [....]}, tracker_id: {"bbox": [....]}, tracker_id: {"bbox": [....]}}  (same for referees and ball)
            "referees": [],     
            "ball": []
        }

        start_time = time.time()

        if self.verbose:
            logger.info(f"[Device: {get_device()}] Starting object tracking at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        for frame_num, detection in enumerate(detections):
            cls_names = detection.names
            cls_names_switched = {v: k for k, v in cls_names.items()}       # swap keys and values, e.g. ball: 1 --> 1: ball for easier access

            # convert to supervision detection format
            detection_supervision = sv.Detections.from_ultralytics(detection)      # xyxy bboxes
            
            # convert goalkeeper to player
            # goalkeepers might get predicted as players in some frames and that could cause tracking issues
            for index, class_id in enumerate(detection_supervision.class_id):
                if cls_names[class_id] == "goalkeeper":
                    detection_supervision.class_id[index] = cls_names_switched["player"]
            # before:
            # class_id=array([1, 2, 2, 2, 2, 3, 3]), tracker_id=None, data={'class_name': array(['goalkeeper', 'player', 'player', 'player', 'player', 'referee', 'referee'], dtype='<U7')}
            # after:          ^
            # class_id=array([2, 2, 2, 2, 2, 3, 3]), tracker_id=None, data={'class_name': array(['goalkeeper', 'player', 'player', 'player', 'player', 'referee', 'referee'], dtype='<U7')}
            
            # track objects
            detections_with_tracks = self.tracker.update_with_detections(detection_supervision)    # adds tracker object to detections, every object gets a unique tracker id
            # example:
            # class_id=array([2, 2, 2, 2, 2, 3, 3]), tracker_id=array([ 1,  2,  3,  4,  5,  6,  7]), data={'class_name': array(['player', 'player', 'player', 'player', 'player', 'referee', 'referee'], dtype='<U7')}

            tracks["players"].append({}) 
            tracks["referees"].append({})
            tracks["ball"].append({})

            for frame_detection in detections_with_tracks:
                # frame_detection: Detections (bboxes), mask, confidence, class_id, tracker_id, class_name
                bbox = frame_detection[0].tolist()
                class_id = frame_detection[3]
                tracker_id = frame_detection[4]

                # add object at class (players/referees/ball) at index (frame) with its unique tracker ID
                if class_id == cls_names_switched["player"]:
                    tracks["players"][frame_num][tracker_id] = {"bbox": bbox}

                if class_id == cls_names_switched["referee"]:
                    tracks["referees"][frame_num][tracker_id] = {"bbox": bbox}

            # no tracker for the ball as there is only one
            for frame_detection in detection_supervision:
                bbox = frame_detection[0].tolist()
                class_id = frame_detection[3]

                if class_id == cls_names_switched["ball"] and frame_detection[2] >= 0.3:    # higher confidence for ball to avoid tracking of field parts etc.
                    tracks["ball"][frame_num][1] = {"bbox": bbox}   # ID 1 as there is only one ball

        if self.verbose:
            logger.info(f"Tracked objects in {len(frames)} frames in {time.time() - start_time:.2f} seconds.")

            separator = f"{'-'*10} [End of tracking] at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {'-'*10}"
            logger.info(separator)

        return tracks
    
    def add_position_to_tracks(self, tracks: Dict[str, List[Dict]]) -> None:
        for object, object_tracks in tracks.items():
            for frame_num, track_dict in enumerate(object_tracks):
                for tracker_id, track in track_dict.items():
                    bbox = track["bbox"]

                    if object == "ball":
                        position = get_center_of_bbox(bbox)
                    else:   # player
                        position = get_foot_position(bbox)

                    # add new key position
                    tracks[object][frame_num][tracker_id]["position"] = position
    
    def draw_annotations(self, frames: List[np.ndarray], tracks: Dict[str, List[Dict]], ball_possession: np.ndarray) -> List[np.ndarray]:   # TODO extra folder for custom drawings and then import?
        output_frames = []  # frames after changing the annotations
        num_interpolated = 0

        for frame_num, frame in enumerate(frames):
            frame = frame.copy()       # don't change original

            player_dict = tracks["players"][frame_num]
            referee_dict = tracks["referees"][frame_num]
            ball_dict = tracks["ball"][frame_num]

            if options["players"] in self.classes:
                for tracker_id, player in player_dict.items():
                    colour = player.get("team_colour", (255, 255, 255))         # get team colour if it exists, else white 
                    frame = ellipse(frame, player["bbox"], colour, tracker_id)

                    if player.get("has_ball", False):
                        frame = triangle(frame, player["bbox"], (0, 0, 255))    # red triangle

            if options["referees"] in self.classes: 
                for _, referee in referee_dict.items():
                    frame = ellipse(frame, referee["bbox"], (0, 255, 255))      # yellow ellipse

            if options["ball"] in self.classes:
                if self.interpolation_tracker[frame_num] == 1:
                    num_interpolated += 1
                else:
                    num_interpolated = 0 
                
                for tracker_id, ball in ball_dict.items():
                    # only draw detected ball or if not too many consecutive interpolated trackings 
                    if num_interpolated <= 25 or self.interpolation_tracker[frame_num] == 0:
                        frame = triangle(frame, ball["bbox"], (0, 255, 0))          # green triangle
            
            if options["stats"] in self.classes: 
                frame = ball_possession_box(frame_num, frame, ball_possession)

            output_frames.append(frame)

        return output_frames