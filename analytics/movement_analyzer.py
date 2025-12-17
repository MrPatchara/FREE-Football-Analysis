"""
Movement Analyzer Module
วิเคราะห์การเคลื่อนไหวของผู้เล่นจาก tracking data
"""
import numpy as np
import cv2
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from scipy.ndimage import gaussian_filter
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    plt = None


class MovementAnalyzer:
    """Analyze player movement from tracking data"""
    
    def __init__(self, fps: int = 30, field_width: int = 1920, field_height: int = 1080):
        """
        Initialize movement analyzer
        
        Args:
            fps: Frames per second of the video
            field_width: Field width in pixels
            field_height: Field height in pixels
        """
        self.fps = fps
        self.field_width = field_width
        self.field_height = field_height
        self.frame_time = 1.0 / fps if fps > 0 else 1.0 / 30.0  # Time per frame in seconds
    
    def get_player_positions_over_time(self, tracks: Dict[str, List[Dict]], player_id: Optional[int] = None, team_id: Optional[int] = None) -> Dict[int, List[Tuple[float, float, int]]]:
        """
        Extract position history for players
        Returns: {player_id: [(x, y, frame_num), ...]}
        """
        player_positions = defaultdict(list)
        
        for frame_num, frame_players in enumerate(tracks.get("players", [])):
            for pid, player in frame_players.items():
                # Filter by player_id if specified
                if player_id is not None and pid != player_id:
                    continue
                
                # Filter by team_id if specified
                if team_id is not None and player.get("team") != team_id:
                    continue
                
                # Get position
                if "position" in player:
                    pos = player["position"]
                    if isinstance(pos, (list, tuple, np.ndarray)) and len(pos) >= 2:
                        player_positions[pid].append((float(pos[0]), float(pos[1]), frame_num))
                elif "bbox" in player:
                    # Fallback: use bbox center
                    bbox = player["bbox"]
                    if len(bbox) >= 4:
                        x = (bbox[0] + bbox[2]) / 2
                        y = (bbox[1] + bbox[3]) / 2
                        player_positions[pid].append((float(x), float(y), frame_num))
        
        return dict(player_positions)
    
    def calculate_distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """Calculate Euclidean distance between two positions"""
        return np.sqrt((pos2[0] - pos1[0])**2 + (pos2[1] - pos1[1])**2)
    
    def calculate_speed_over_time(self, positions: List[Tuple[float, float, int]]) -> List[Tuple[float, int]]:
        """
        Calculate speed for each frame transition
        Returns: [(speed_pixels_per_second, frame_num), ...]
        """
        speeds = []
        
        if len(positions) < 2:
            return speeds
        
        for i in range(1, len(positions)):
            x1, y1, frame1 = positions[i-1]
            x2, y2, frame2 = positions[i]
            
            distance = self.calculate_distance((x1, y1), (x2, y2))
            time_diff = (frame2 - frame1) * self.frame_time
            
            if time_diff > 0:
                speed = distance / time_diff
            else:
                speed = 0.0
            
            speeds.append((speed, frame2))
        
        return speeds
    
    def calculate_total_distance(self, positions: List[Tuple[float, float, int]]) -> float:
        """Calculate total distance traveled"""
        total = 0.0
        
        for i in range(1, len(positions)):
            x1, y1, _ = positions[i-1]
            x2, y2, _ = positions[i]
            total += self.calculate_distance((x1, y1), (x2, y2))
        
        return total
    
    def calculate_acceleration(self, speeds: List[Tuple[float, int]]) -> List[Tuple[float, int]]:
        """
        Calculate acceleration from speed changes
        Returns: [(acceleration_pixels_per_second_squared, frame_num), ...]
        """
        accelerations = []
        
        if len(speeds) < 2:
            return accelerations
        
        for i in range(1, len(speeds)):
            speed1, frame1 = speeds[i-1]
            speed2, frame2 = speeds[i]
            
            speed_diff = speed2 - speed1
            time_diff = (frame2 - frame1) * self.frame_time
            
            if time_diff > 0:
                acceleration = speed_diff / time_diff
            else:
                acceleration = 0.0
            
            accelerations.append((acceleration, frame2))
        
        return accelerations
    
    def analyze_player_movement(self, tracks: Dict[str, List[Dict]], player_id: Optional[int] = None, team_id: Optional[int] = None) -> Dict:
        """
        Complete movement analysis for players
        
        Returns:
            Dictionary with movement statistics for each player
        """
        player_positions = self.get_player_positions_over_time(tracks, player_id, team_id)
        
        analysis = {}
        
        for pid, positions in player_positions.items():
            if len(positions) < 2:
                continue
            
            speeds = self.calculate_speed_over_time(positions)
            accelerations = self.calculate_acceleration(speeds) if speeds else []
            total_distance = self.calculate_total_distance(positions)
            
            speed_values = [s[0] for s in speeds] if speeds else [0.0]
            acceleration_values = [a[0] for a in accelerations] if accelerations else [0.0]
            
            analysis[pid] = {
                "positions": positions,
                "speeds": speeds,
                "accelerations": accelerations,
                "total_distance": total_distance,
                "avg_speed": np.mean(speed_values) if speed_values else 0.0,
                "max_speed": np.max(speed_values) if speed_values else 0.0,
                "min_speed": np.min(speed_values) if speed_values else 0.0,
                "avg_acceleration": np.mean(acceleration_values) if acceleration_values else 0.0,
                "max_acceleration": np.max(acceleration_values) if acceleration_values else 0.0,
                "max_deceleration": np.min(acceleration_values) if acceleration_values else 0.0,
                "total_time": len(positions) * self.frame_time,
                "num_frames": len(positions)
            }
        
        return analysis
    
    def draw_movement_path(self, positions: List[Tuple[float, float, int]], image: np.ndarray, color: Tuple[int, int, int] = (255, 0, 0), thickness: int = 2) -> np.ndarray:
        """
        Draw movement path on image
        
        Args:
            positions: List of (x, y, frame) tuples
            image: Image to draw on
            color: BGR color tuple
            thickness: Line thickness
            
        Returns:
            Image with path drawn
        """
        result = image.copy()
        
        if len(positions) < 2:
            return result
        
        points = []
        for x, y, _ in positions:
            if 0 <= x < self.field_width and 0 <= y < self.field_height:
                points.append((int(x), int(y)))
        
        if len(points) < 2:
            return result
        
        # Draw path
        for i in range(1, len(points)):
            cv2.line(result, points[i-1], points[i], color, thickness)
        
        # Draw start point (green circle)
        if points:
            cv2.circle(result, points[0], 8, (0, 255, 0), -1)
        
        # Draw end point (red circle)
        if len(points) > 1:
            cv2.circle(result, points[-1], 8, (0, 0, 255), -1)
        
        return result
    
    def generate_speed_zones_heat_map(
        self,
        tracks: Dict[str, List[Dict]],
        speed_threshold: float,
        team_id: Optional[int] = None,
        sigma: float = 30.0
    ) -> np.ndarray:
        """
        Generate heat map showing areas where players exceeded speed threshold
        
        Args:
            tracks: Tracking data
            speed_threshold: Speed threshold in pixels per second
            team_id: Optional team filter
            sigma: Gaussian blur sigma
            
        Returns:
            Heat map image (BGR format)
        """
        # Get all positions where speed > threshold
        analysis = self.analyze_player_movement(tracks, team_id=team_id)
        
        high_speed_positions = []
        
        for pid, data in analysis.items():
            speeds = data["speeds"]
            positions = data["positions"]
            
            # Create a mapping from frame to speed
            speed_by_frame = {frame: speed for speed, frame in speeds}
            
            for x, y, frame in positions[1:]:  # Skip first position (no speed)
                speed = speed_by_frame.get(frame, 0.0)
                if speed > speed_threshold:
                    high_speed_positions.append((x, y))
        
        if not high_speed_positions:
            # Return empty heat map
            return np.zeros((self.field_height, self.field_width, 3), dtype=np.uint8)
        
        # Create heat map
        heat_map = np.zeros((self.field_height, self.field_width), dtype=np.float32)
        
        for x, y in high_speed_positions:
            if 0 <= x < self.field_width and 0 <= y < self.field_height:
                heat_map[int(y), int(x)] += 1.0
        
        # Apply Gaussian filter
        if sigma > 0:
            heat_map = gaussian_filter(heat_map, sigma=sigma)
        
        # Normalize
        if heat_map.max() > 0:
            heat_map = heat_map / heat_map.max()
        
        # Apply colormap
        heat_map_uint8 = (heat_map * 255).astype(np.uint8)
        heat_map_colored = cv2.applyColorMap(heat_map_uint8, cv2.COLORMAP_JET)
        
        return heat_map_colored
    
    def create_speed_chart(self, speeds: List[Tuple[float, int]], title: str = "Player Speed Over Time") -> np.ndarray:
        """
        Create a speed chart image
        
        Args:
            speeds: List of (speed, frame) tuples
            title: Chart title
            
        Returns:
            Chart image as numpy array (BGR format)
        """
        if not MATPLOTLIB_AVAILABLE or not speeds:
            # Return empty image if matplotlib not available
            return np.zeros((400, 800, 3), dtype=np.uint8)
        
        frames = [s[1] for s in speeds]
        speed_values = [s[0] for s in speeds]
        
        # Convert frames to time (seconds)
        times = [f * self.frame_time for f in frames]
        
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(times, speed_values, linewidth=2, color='blue')
        ax.set_xlabel('Time (seconds)', fontsize=12)
        ax.set_ylabel('Speed (pixels/second)', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.fill_between(times, speed_values, alpha=0.3)
        
        plt.tight_layout()
        
        # Convert to numpy array
        fig.canvas.draw()
        buf = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
        buf = buf.reshape(fig.canvas.get_width_height()[::-1] + (3,))
        
        plt.close(fig)
        
        # Convert RGB to BGR
        buf_bgr = cv2.cvtColor(buf, cv2.COLOR_RGB2BGR)
        
        return buf_bgr
    
    def get_team_average_positions(self, tracks: Dict[str, List[Dict]], team_id: int) -> Tuple[float, float]:
        """
        Calculate average position for a team
        
        Returns:
            (avg_x, avg_y)
        """
        positions = []
        
        for frame_players in tracks.get("players", []):
            for pid, player in frame_players.items():
                if player.get("team") == team_id:
                    if "position" in player:
                        pos = player["position"]
                        if isinstance(pos, (list, tuple, np.ndarray)) and len(pos) >= 2:
                            positions.append((float(pos[0]), float(pos[1])))
        
        if not positions:
            return (self.field_width / 2, self.field_height / 2)
        
        avg_x = np.mean([p[0] for p in positions])
        avg_y = np.mean([p[1] for p in positions])
        
        return (avg_x, avg_y)
