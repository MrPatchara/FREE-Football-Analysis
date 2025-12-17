"""
Statistics Calculator Module
คำนวณสถิติต่างๆ จาก tracking data
"""
import numpy as np
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


class StatisticsCalculator:
    """Calculate statistics from tracking data"""
    
    def __init__(self, fps: int = 30):
        """
        Initialize statistics calculator
        
        Args:
            fps: Frames per second of the video
        """
        self.fps = fps
        self.frame_time = 1.0 / fps if fps > 0 else 1.0 / 30.0  # Time per frame in seconds
    
    def calculate_distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """
        Calculate Euclidean distance between two positions
        
        Args:
            pos1: First position (x, y)
            pos2: Second position (x, y)
            
        Returns:
            Distance in pixels
        """
        return np.sqrt((pos2[0] - pos1[0])**2 + (pos2[1] - pos1[1])**2)
    
    def calculate_speed(self, distance: float, time: float) -> float:
        """
        Calculate speed from distance and time
        
        Args:
            distance: Distance in pixels
            time: Time in seconds
            
        Returns:
            Speed in pixels per second
        """
        if time <= 0:
            return 0.0
        return distance / time
    
    def pixels_to_meters(self, pixels: float, field_length_pixels: float = 1920, field_length_meters: float = 105.0) -> float:
        """
        Convert pixels to meters
        
        Args:
            pixels: Distance in pixels
            field_length_pixels: Field length in pixels (default 1920)
            field_length_meters: Field length in meters (default 105m for standard football field)
            
        Returns:
            Distance in meters
        """
        return (pixels / field_length_pixels) * field_length_meters
    
    def calculate_player_statistics(self, tracks: Dict[str, List[Dict]], field_width: int = 1920, field_height: int = 1080) -> Dict:
        """
        Calculate accurate statistics from tracking data
        Only calculates values that are accurate and don't require field size conversion
        
        Args:
            tracks: Tracking data dictionary
            field_width: Field width in pixels (not used for calculations)
            field_height: Field height in pixels (not used for calculations)
            
        Returns:
            Dictionary containing accurate statistics
        """
        stats = {
            "teams": {
                1: {
                    "ball_possession_percent": 0.0,
                    "ball_possession_frames": 0,
                    "ball_possession_time_seconds": 0.0,
                    "total_touches": 0,
                    "active_frames": 0,
                    "unique_players": set()
                },
                2: {
                    "ball_possession_percent": 0.0,
                    "ball_possession_frames": 0,
                    "ball_possession_time_seconds": 0.0,
                    "total_touches": 0,
                    "active_frames": 0,
                    "unique_players": set()
                }
            },
            "overall": {
                "total_frames": len(tracks.get("players", [])),
                "total_players_team1": 0,
                "total_players_team2": 0,
                "total_ball_possession_frames": 0
            }
        }
        
        ball_possession_frames = {1: 0, 2: 0}
        touches = defaultdict(int)
        active_frames = defaultdict(int)
        unique_players = {1: set(), 2: set()}
        
        # Check if ball_possession array is available (more accurate than has_ball flags)
        ball_possession_array = tracks.get("ball_possession")
        use_ball_possession_array = False
        if ball_possession_array is not None:
            # Convert to numpy array if it's not already
            if not isinstance(ball_possession_array, np.ndarray):
                try:
                    ball_possession_array = np.array(ball_possession_array)
                except:
                    ball_possession_array = None
            if ball_possession_array is not None and len(ball_possession_array) > 0:
                use_ball_possession_array = True
        
        # Process each frame
        players_list = tracks.get("players", [])
        if not players_list:
            return stats
        
        total_frames_with_players = 0
        for frame_num, frame_players in enumerate(players_list):
            # Skip if frame_players is empty or not a dict
            if not isinstance(frame_players, dict) or len(frame_players) == 0:
                continue
            
            total_frames_with_players += 1
            
            # Count ball possession from ball_possession array if available (more accurate)
            if use_ball_possession_array and frame_num < len(ball_possession_array):
                team_with_ball = int(ball_possession_array[frame_num])
                if team_with_ball in [1, 2]:
                    ball_possession_frames[team_with_ball] += 1
                    stats["teams"][team_with_ball]["ball_possession_frames"] += 1
            
            for pid, player in frame_players.items():
                # Skip if player is not a dict
                if not isinstance(player, dict):
                    continue
                
                team = player.get("team")
                
                # Only process if team is assigned (1 or 2)
                if team not in [1, 2]:
                    continue
                
                # Count active frames (players detected in frame)
                active_frames[pid] += 1
                stats["teams"][team]["active_frames"] += 1
                unique_players[team].add(pid)
                
                # Count touches from has_ball flag (for touch statistics)
                if player.get("has_ball", False):
                    touches[pid] += 1
                    stats["teams"][team]["total_touches"] += 1
                    
                    # Only use has_ball for possession if ball_possession_array is not available
                    if not use_ball_possession_array:
                        ball_possession_frames[team] += 1
                        stats["teams"][team]["ball_possession_frames"] += 1
        
        # Update total frames if we found frames with players
        if total_frames_with_players > 0:
            stats["overall"]["total_frames"] = total_frames_with_players
        
        # Calculate team statistics
        total_possession_frames = ball_possession_frames[1] + ball_possession_frames[2]
        stats["overall"]["total_ball_possession_frames"] = total_possession_frames
        
        for team_id in [1, 2]:
            team_stats = stats["teams"][team_id]
            
            # Ball possession percentage
            if total_possession_frames > 0:
                team_stats["ball_possession_percent"] = (
                    ball_possession_frames[team_id] / total_possession_frames
                ) * 100
            
            # Ball possession time in seconds
            team_stats["ball_possession_time_seconds"] = (
                ball_possession_frames[team_id] * self.frame_time
            )
            
            # Number of unique players
            team_stats["total_players"] = len(unique_players[team_id])
            stats["overall"][f"total_players_team{team_id}"] = len(unique_players[team_id])
        
        # Convert sets to counts for JSON serialization
        for team_id in [1, 2]:
            stats["teams"][team_id]["unique_players"] = len(stats["teams"][team_id]["unique_players"])
        
        return stats
    
    def get_summary_statistics(self, stats: Dict) -> Dict:
        """
        Get summary statistics for display (only accurate values)
        
        Args:
            stats: Statistics dictionary from calculate_player_statistics
            
        Returns:
            Summary statistics dictionary
        """
        summary = {
            "teams": {
                1: {
                    "ball_possession_percent": stats["teams"][1]["ball_possession_percent"],
                    "ball_possession_frames": stats["teams"][1]["ball_possession_frames"],
                    "ball_possession_time_seconds": stats["teams"][1]["ball_possession_time_seconds"],
                    "ball_possession_time_minutes": stats["teams"][1]["ball_possession_time_seconds"] / 60.0,
                    "total_touches": stats["teams"][1]["total_touches"],
                    "total_players": stats["teams"][1]["total_players"],
                    "active_frames": stats["teams"][1]["active_frames"]
                },
                2: {
                    "ball_possession_percent": stats["teams"][2]["ball_possession_percent"],
                    "ball_possession_frames": stats["teams"][2]["ball_possession_frames"],
                    "ball_possession_time_seconds": stats["teams"][2]["ball_possession_time_seconds"],
                    "ball_possession_time_minutes": stats["teams"][2]["ball_possession_time_seconds"] / 60.0,
                    "total_touches": stats["teams"][2]["total_touches"],
                    "total_players": stats["teams"][2]["total_players"],
                    "active_frames": stats["teams"][2]["active_frames"]
                }
            },
            "overall": {
                "total_frames": stats["overall"]["total_frames"],
                "total_players_team1": stats["overall"]["total_players_team1"],
                "total_players_team2": stats["overall"]["total_players_team2"],
                "total_ball_possession_frames": stats["overall"]["total_ball_possession_frames"],
                "video_duration_seconds": stats["overall"]["total_frames"] * self.frame_time,
                "video_duration_minutes": (stats["overall"]["total_frames"] * self.frame_time) / 60.0
            }
        }
        
        return summary

