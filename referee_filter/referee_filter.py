"""
Referee Filter Module
Filters out referees from player tracks using multiple methods:
1. Cross-reference with detected referees
2. Color analysis (referees typically wear black/yellow/red)
3. Position analysis (referees often stay near sidelines)
4. Size analysis (referees may have different average sizes)
"""

from typing import List, Dict, Set, Tuple
import numpy as np


class RefereeFilter:
    """
    Filters referees from player tracks using multiple heuristics.
    """
    
    def __init__(self, iou_threshold: float = 0.3, color_tolerance: int = 40):
        """
        Initialize referee filter.
        
        Args:
            iou_threshold: IoU threshold for bbox overlap detection (0.0-1.0)
            color_tolerance: Color difference tolerance for referee color detection
        """
        self.iou_threshold = iou_threshold
        self.color_tolerance = color_tolerance
        
        # Typical referee colors (black, yellow, red, blue)
        self.referee_colors = [
            (0, 0, 0),        # Black
            (255, 255, 0),   # Yellow
            (255, 0, 0),     # Red
            (0, 0, 255),     # Blue
            (255, 140, 0),   # Orange
        ]
    
    def calculate_iou(self, bbox1: List[float], bbox2: List[float]) -> float:
        """
        Calculate Intersection over Union (IoU) between two bounding boxes.
        
        Args:
            bbox1: [x1, y1, x2, y2]
            bbox2: [x1, y1, x2, y2]
            
        Returns:
            IoU value between 0.0 and 1.0
        """
        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2
        
        # Calculate intersection
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)
        
        if x2_i <= x1_i or y2_i <= y1_i:
            return 0.0
        
        intersection = (x2_i - x1_i) * (y2_i - y1_i)
        
        # Calculate union
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def is_referee_color(self, color: Tuple[float, float, float]) -> bool:
        """
        Check if a color matches typical referee colors.
        
        Args:
            color: RGB color tuple
            
        Returns:
            True if color matches referee colors
        """
        if isinstance(color, np.ndarray):
            color = tuple(color.tolist())
        elif isinstance(color, list):
            color = tuple(color)
        
        if not isinstance(color, tuple) or len(color) != 3:
            return False
        
        for ref_color in self.referee_colors:
            # Calculate color distance
            distance = np.sqrt(
                (color[0] - ref_color[0])**2 +
                (color[1] - ref_color[1])**2 +
                (color[2] - ref_color[2])**2
            )
            if distance < self.color_tolerance:
                return True
        
        return False
    
    def filter_by_referee_tracks(self, tracks: Dict[str, List[Dict]]) -> Set[int]:
        """
        Filter player IDs that overlap with detected referee tracks.
        
        Args:
            tracks: Dictionary with "players" and "referees" keys
            
        Returns:
            Set of player tracker IDs that should be filtered out
        """
        filtered_ids = set()
        
        if "referees" not in tracks or "players" not in tracks:
            return filtered_ids
        
        # For each frame, check for overlaps between players and referees
        for frame_num in range(len(tracks["players"])):
            frame_players = tracks["players"][frame_num]
            frame_referees = tracks["referees"][frame_num] if frame_num < len(tracks["referees"]) else {}
            
            if not isinstance(frame_players, dict) or not isinstance(frame_referees, dict):
                continue
            
            # Check each player against each referee
            for player_id, player in frame_players.items():
                if "bbox" not in player:
                    continue
                
                player_bbox = player["bbox"]
                
                for referee_id, referee in frame_referees.items():
                    if "bbox" not in referee:
                        continue
                    
                    referee_bbox = referee["bbox"]
                    
                    # Calculate IoU
                    iou = self.calculate_iou(player_bbox, referee_bbox)
                    
                    # If significant overlap, mark player as referee
                    if iou > self.iou_threshold:
                        filtered_ids.add(player_id)
        
        return filtered_ids
    
    def filter_by_color_analysis(self, frames: List[np.ndarray], tracks: Dict[str, List[Dict]], 
                                  player_ids_to_check: Set[int] = None) -> Set[int]:
        """
        Filter players based on color analysis (referees wear specific colors).
        
        Args:
            frames: List of video frames
            tracks: Dictionary with "players" key
            player_ids_to_check: Optional set of player IDs to check (if None, checks all)
            
        Returns:
            Set of player tracker IDs that should be filtered out
        """
        filtered_ids = set()
        
        if "players" not in tracks:
            return filtered_ids
        
        # Track color consistency for each player
        player_colors = {}  # player_id -> list of colors across frames
        
        for frame_num, frame_players in enumerate(tracks["players"]):
            if frame_num >= len(frames):
                break
            
            if not isinstance(frame_players, dict):
                continue
            
            frame = frames[frame_num]
            
            for player_id, player in frame_players.items():
                # Skip if we're only checking specific IDs
                if player_ids_to_check is not None and player_id not in player_ids_to_check:
                    continue
                
                if "bbox" not in player:
                    continue
                
                bbox = player["bbox"]
                team_color = player.get("team_colour")
                
                # If player has a team color, check if it matches referee colors
                if team_color is not None:
                    if self.is_referee_color(team_color):
                        filtered_ids.add(player_id)
                        continue
                
                # Extract color from shirt area
                try:
                    x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
                    x1 = max(0, min(x1, frame.shape[1]))
                    y1 = max(0, min(y1, frame.shape[0]))
                    x2 = max(0, min(x2, frame.shape[1]))
                    y2 = max(0, min(y2, frame.shape[0]))
                    
                    if x2 > x1 and y2 > y1:
                        # Extract top half (shirt area)
                        shirt_area = frame[y1:int(y1 + (y2 - y1) * 0.5), x1:x2]
                        
                        if shirt_area.size > 0:
                            # Calculate mean color
                            mean_color = np.mean(shirt_area.reshape(-1, 3), axis=0)
                            
                            if self.is_referee_color(mean_color):
                                filtered_ids.add(player_id)
                                
                                if player_id not in player_colors:
                                    player_colors[player_id] = []
                                player_colors[player_id].append(mean_color)
                except Exception:
                    continue
        
        # Additional check: if a player consistently has referee-like colors across frames
        for player_id, colors in player_colors.items():
            if len(colors) >= 3:  # Need at least 3 frames
                referee_color_count = sum(1 for c in colors if self.is_referee_color(c))
                if referee_color_count / len(colors) > 0.6:  # 60% of frames show referee color
                    filtered_ids.add(player_id)
        
        return filtered_ids
    
    def filter_referees(self, frames: List[np.ndarray], tracks: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """
        Main method to filter referees from player tracks.
        
        Args:
            frames: List of video frames
            tracks: Dictionary with "players" and "referees" keys
            
        Returns:
            Filtered tracks dictionary with referees removed from players
        """
        # Method 1: Filter by overlap with detected referees
        filtered_by_overlap = self.filter_by_referee_tracks(tracks)
        
        # Method 2: Filter by color analysis
        filtered_by_color = self.filter_by_color_analysis(frames, tracks, filtered_by_overlap)
        
        # Combine both methods
        all_filtered_ids = filtered_by_overlap | filtered_by_color
        
        # Remove filtered players from tracks
        if all_filtered_ids and "players" in tracks:
            for frame_num, frame_players in enumerate(tracks["players"]):
                if not isinstance(frame_players, dict):
                    continue
                
                # Remove filtered player IDs
                for player_id in list(frame_players.keys()):
                    if player_id in all_filtered_ids:
                        del frame_players[player_id]
        
        return tracks

