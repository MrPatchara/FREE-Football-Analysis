from typing import Union, List, Optional
import os
import sys
import argparse
import warnings
from utils import read_video, save_video, options
from trackers import Tracker
from team_assignment import TeamAssigner
from player_ball_assignment import PlayerBallAssigner
from camera_movement import CameraMovementEstimator
from referee_filter import RefereeFilter

def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Development mode
        base_path = os.path.abspath(os.path.dirname(__file__))
    
    return os.path.join(base_path, relative_path)

def process_video(data: Union[str, bytes], classes: List[int], verbose: bool=True, output_path: Optional[str] = None, return_tracks: bool = False) -> Union[str, tuple]:
    """
    Process video and return output path
    
    Args:
        data: Video data (file path or bytes)
        classes: List of class IDs to track
        verbose: Enable verbose logging
        output_path: Output video path (optional)
        return_tracks: If True, return (output_path, tracks) tuple
        
    Returns:
        output_path if return_tracks=False, else (output_path, tracks)
    """
    from datetime import datetime
    
    frames, fps, _, _ = read_video(data, verbose)

    # Get model path (works in both dev and PyInstaller bundle mode)
    model_path = get_resource_path("models/best.pt")
    tracker = Tracker(model_path, classes, verbose)
    tracks = tracker.get_object_tracks(frames)
    tracker.add_position_to_tracks(tracks)

    # Filter referees from player tracks
    if verbose:
        print("Filtering referees from player tracks...")
    referee_filter = RefereeFilter(iou_threshold=0.3, color_tolerance=40)
    tracks = referee_filter.filter_referees(frames, tracks)
    if verbose:
        print("Referee filtering completed.")

    camera_movement_estimator = CameraMovementEstimator(frames[0], classes, verbose)
    camera_movement_per_frame = camera_movement_estimator.get_camera_movement(frames)
    camera_movement_estimator.adjust_positions_to_tracks(tracks, camera_movement_per_frame)

    tracks["ball"] = tracker.interpolate_ball_positions(tracks["ball"])

    team_assigner = TeamAssigner()
    team_assigner.get_teams(frames, tracks)

    player_assigner = PlayerBallAssigner()
    player_assigner.get_player_and_possession(tracks)

    # Store ball_possession in tracks for statistics calculation
    if player_assigner.ball_possession is not None:
        tracks["ball_possession"] = player_assigner.ball_possession

    output = tracker.draw_annotations(frames, tracks, player_assigner.ball_possession)
    output = camera_movement_estimator.draw_camera_movement(output, camera_movement_per_frame)

    # Generate output filename with timestamp
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Use absolute path - prefer executable directory in PyInstaller bundle mode
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller bundle mode - save to executable directory
            exe_dir = os.path.dirname(sys.executable)
            output_dir = os.path.join(exe_dir, "output")
        else:
            # Development mode - save to project output directory
            output_dir = "output"
        
        # Create output directory if it doesn't exist
        try:
            os.makedirs(output_dir, exist_ok=True)
            if verbose:
                print(f"Output directory: {output_dir}")
        except Exception as e:
            if verbose:
                print(f"Warning: Could not create output directory {output_dir}: {e}")
            # Fallback to current directory
            output_dir = "."
        
        output_path = os.path.join(output_dir, f"output_{timestamp}.mp4")
    
    save_video(output, output_path, fps, verbose)
    
    if return_tracks:
        return output_path, tracks
    return output_path

def _video(path: str) -> None:
    if not path.lower().endswith(".mp4"):
        raise argparse.ArgumentTypeError(f"File '{path}' is not an MP4 file.")
    
    if not os.path.isfile(path):
        raise argparse.ArgumentTypeError(f"File '{path}' does not exist.") 
    
def _classes(classes: List[str]) -> List[int]:
    class_ids = [value for key, value in options.items() if key in classes]
    
    invalid_classes = [cls for cls in classes if cls not in options.keys()]
    
    # all classes invalid, raise error
    if len(invalid_classes) == len(options):
        raise argparse.ArgumentTypeError("Classes are invalid.")

    # continue with the subset of valid classes
    if invalid_classes:
        warnings.warn(f"Invalid classes: {', '.join(invalid_classes)}. Valid options are: {', '.join(options.keys())}. Continuing with subset of valid classes.")
    
    return class_ids

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FREE Football Analysis - Automated football match analysis using Computer Vision.")

    parser.add_argument("--video", type=str, help="Video path of the video (must be .mp4)")
    parser.add_argument("--tracks", nargs="+", type=str, help="Select the objects to visualise: players, goalkeepers, referees, ball")
    parser.add_argument("--verbose", action="store_true", help="Model output and logging")

    args = parser.parse_args()
    
    if args.video and args.tracks:
        _video(args.video)
        classes = _classes(args.tracks)
        
        process_video(args.video, classes, args.verbose)