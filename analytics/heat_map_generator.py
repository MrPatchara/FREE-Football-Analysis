"""
Heat Map Generator Module
สร้าง Heat Maps จาก tracking data สำหรับผู้เล่น, ลูกบอล, และทีม
"""
import numpy as np
import cv2
from typing import List, Dict, Tuple, Optional
from scipy.ndimage import gaussian_filter
try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
except ImportError:
    plt = None


class HeatMapGenerator:
    """Generate heat maps from tracking data"""
    
    def __init__(self, field_width: int = 1920, field_height: int = 1080):
        """
        Initialize heat map generator
        
        Args:
            field_width: ความกว้างของสนาม (pixels)
            field_height: ความสูงของสนาม (pixels)
        """
        self.field_width = field_width
        self.field_height = field_height
        self.heat_map = np.zeros((field_height, field_width), dtype=np.float32)
        
    def generate_heat_map(
        self, 
        positions: List[Tuple[float, float]], 
        sigma: float = 30.0,
        alpha: float = 0.6
    ) -> np.ndarray:
        """
        สร้าง heat map จากตำแหน่งต่างๆ
        
        Args:
            positions: List of (x, y) positions
            sigma: ความเบลอของ heat map (ยิ่งมากยิ่งเบลอ)
            alpha: ความโปร่งใส (0-1)
            
        Returns:
            Heat map image (BGR format)
        """
        # สร้าง heat map ใหม่
        heat_map = np.zeros((self.field_height, self.field_width), dtype=np.float32)
        
        # เพิ่มค่าในตำแหน่งที่มีการเคลื่อนไหว
        for x, y in positions:
            if 0 <= x < self.field_width and 0 <= y < self.field_height:
                heat_map[int(y), int(x)] += 1.0
        
        # ใช้ Gaussian filter เพื่อทำให้ smooth
        if sigma > 0:
            heat_map = gaussian_filter(heat_map, sigma=sigma)
        
        # Normalize 0-1
        if heat_map.max() > 0:
            heat_map = heat_map / heat_map.max()
        
        # แปลงเป็นสี (ใช้ colormap แบบ jet)
        heat_map_colored = self._apply_colormap(heat_map, alpha)
        
        return heat_map_colored
    
    def _apply_colormap(self, heat_map: np.ndarray, alpha: float = 0.6) -> np.ndarray:
        """
        ใช้ colormap กับ heat map
        
        Args:
            heat_map: Normalized heat map (0-1)
            alpha: ความโปร่งใส
            
        Returns:
            BGRA image
        """
        if plt is None:
            # Fallback: ใช้ OpenCV colormap ถ้าไม่มี matplotlib
            heat_map_uint8 = (heat_map * 255).astype(np.uint8)
            heat_map_colored = cv2.applyColorMap(heat_map_uint8, cv2.COLORMAP_JET)
            alpha_channel = (heat_map * alpha * 255).astype(np.uint8)
            heat_map_with_alpha = cv2.merge([heat_map_colored, alpha_channel])
            return heat_map_with_alpha
        
        # สร้าง colormap แบบ jet (สีน้ำเงิน -> เขียว -> เหลือง -> แดง)
        try:
            # สำหรับ matplotlib เวอร์ชันใหม่
            if hasattr(plt, 'colormaps'):
                cmap = plt.colormaps['jet']
            else:
                cmap = plt.cm.get_cmap('jet')
        except (AttributeError, KeyError):
            # Fallback: ใช้ OpenCV colormap
            heat_map_uint8 = (heat_map * 255).astype(np.uint8)
            heat_map_colored = cv2.applyColorMap(heat_map_uint8, cv2.COLORMAP_JET)
            alpha_channel = (heat_map * alpha * 255).astype(np.uint8)
            heat_map_with_alpha = cv2.merge([heat_map_colored, alpha_channel])
            return heat_map_with_alpha
        
        # แปลง heat map เป็นสี
        heat_map_colored = cmap(heat_map)
        
        # แปลง RGBA เป็น BGR และปรับ alpha
        heat_map_bgr = cv2.cvtColor((heat_map_colored[:, :, :3] * 255).astype(np.uint8), cv2.COLOR_RGB2BGR)
        
        # สร้าง alpha channel
        alpha_channel = (heat_map_colored[:, :, 3] * alpha * 255).astype(np.uint8)
        
        # รวม alpha channel
        heat_map_with_alpha = cv2.merge([heat_map_bgr, alpha_channel])
        
        return heat_map_with_alpha
    
    def generate_player_heat_map(
        self, 
        tracks: Dict[str, List[Dict]], 
        team_id: Optional[int] = None,
        player_id: Optional[int] = None,
        sigma: float = 30.0
    ) -> np.ndarray:
        """
        สร้าง heat map สำหรับผู้เล่น
        
        Args:
            tracks: Tracking data dictionary
            team_id: Team ID (1 or 2) ถ้า None จะรวมทุกทีม
            player_id: Player ID ถ้า None จะรวมทุกผู้เล่น
            sigma: ความเบลอ
            
        Returns:
            Heat map image
        """
        positions = []
        
        for frame_num, frame_players in enumerate(tracks.get("players", [])):
            for pid, player in frame_players.items():
                # กรองตาม team_id
                if team_id is not None:
                    if player.get("team") != team_id:
                        continue
                
                # กรองตาม player_id
                if player_id is not None:
                    if pid != player_id:
                        continue
                
                # เก็บตำแหน่ง (ใช้ position ถ้ามี ไม่เช่นนั้นใช้ bbox center)
                if "position" in player:
                    pos = player["position"]
                    if isinstance(pos, (list, tuple, np.ndarray)) and len(pos) >= 2:
                        positions.append((float(pos[0]), float(pos[1])))
                elif "bbox" in player:
                    # Fallback: ใช้ bbox center
                    bbox = player["bbox"]
                    if len(bbox) >= 4:
                        x = (bbox[0] + bbox[2]) / 2
                        y = (bbox[1] + bbox[3]) / 2
                        positions.append((float(x), float(y)))
        
        if not positions:
            # สร้าง empty heat map
            return np.zeros((self.field_height, self.field_width, 4), dtype=np.uint8)
        
        return self.generate_heat_map(positions, sigma)
    
    def generate_ball_heat_map(
        self, 
        tracks: Dict[str, List[Dict]], 
        sigma: float = 25.0
    ) -> np.ndarray:
        """
        สร้าง heat map สำหรับลูกบอล
        
        Args:
            tracks: Tracking data dictionary
            sigma: ความเบลอ
            
        Returns:
            Heat map image
        """
        positions = []
        
        for frame_num, frame_ball in enumerate(tracks.get("ball", [])):
            for bid, ball in frame_ball.items():
                # เก็บตำแหน่ง (ใช้ position ถ้ามี ไม่เช่นนั้นใช้ bbox center)
                if "position" in ball:
                    pos = ball["position"]
                    if isinstance(pos, (list, tuple, np.ndarray)) and len(pos) >= 2:
                        positions.append((float(pos[0]), float(pos[1])))
                elif "bbox" in ball:
                    # Fallback: ใช้ bbox center
                    bbox = ball["bbox"]
                    if len(bbox) >= 4:
                        x = (bbox[0] + bbox[2]) / 2
                        y = (bbox[1] + bbox[3]) / 2
                        positions.append((float(x), float(y)))
        
        if not positions:
            # สร้าง empty heat map
            return np.zeros((self.field_height, self.field_width, 4), dtype=np.uint8)
        
        return self.generate_heat_map(positions, sigma)
    
    def generate_team_heat_map(
        self, 
        tracks: Dict[str, List[Dict]], 
        team_id: int,
        sigma: float = 35.0
    ) -> np.ndarray:
        """
        สร้าง heat map สำหรับทีม
        
        Args:
            tracks: Tracking data dictionary
            team_id: Team ID (1 or 2)
            sigma: ความเบลอ
            
        Returns:
            Heat map image
        """
        return self.generate_player_heat_map(tracks, team_id=team_id, sigma=sigma)
    
    def overlay_heat_map(
        self, 
        background: np.ndarray, 
        heat_map: np.ndarray,
        title: Optional[str] = None
    ) -> np.ndarray:
        """
        วาง heat map บน background image และเพิ่มข้อความกำกับ
        
        Args:
            background: Background image (BGR)
            heat_map: Heat map with alpha channel (BGRA)
            title: ข้อความกำกับที่จะแสดงบนรูป
            
        Returns:
            Combined image
        """
        # Resize heat map ให้ตรงกับ background
        if heat_map.shape[:2] != background.shape[:2]:
            heat_map = cv2.resize(heat_map, (background.shape[1], background.shape[0]))
        
        # แยก alpha channel
        if heat_map.shape[2] == 4:
            heat_map_rgb = heat_map[:, :, :3]
            alpha = heat_map[:, :, 3:4] / 255.0
        else:
            heat_map_rgb = heat_map
            alpha = np.ones((heat_map.shape[0], heat_map.shape[1], 1)) * 0.6
        
        # Blend images
        result = (background.astype(np.float32) * (1 - alpha) + 
                 heat_map_rgb.astype(np.float32) * alpha).astype(np.uint8)
        
        # เพิ่มข้อความกำกับ
        if title:
            result = self.add_title_to_image(result, title)
        
        return result
    
    def add_title_to_image(self, image: np.ndarray, title: str) -> np.ndarray:
        """
        Add title label to image (English text only to avoid encoding issues)
        
        Args:
            image: Input image (BGR)
            title: Title text to display (English only)
            
        Returns:
            Image with title
        """
        result = image.copy()
        
        # Calculate font scale based on image size for better readability
        height, width = image.shape[:2]
        base_font_scale = max(0.8, min(1.5, width / 1000.0))  # Scale based on image width
        font_scale = base_font_scale
        
        # Text settings
        font = cv2.FONT_HERSHEY_SIMPLEX
        thickness = max(2, int(base_font_scale * 2))
        color = (255, 255, 255)  # White text
        bg_color = (0, 0, 0)  # Black background
        
        # Calculate text size
        (text_width, text_height), baseline = cv2.getTextSize(title, font, font_scale, thickness)
        
        # Create background for text (with padding)
        padding = max(10, int(width / 100))  # Adaptive padding
        bg_x1 = padding
        bg_y1 = padding
        bg_x2 = bg_x1 + text_width + padding * 2
        bg_y2 = bg_y1 + text_height + padding * 2
        
        # Draw background
        cv2.rectangle(result, (bg_x1, bg_y1), (bg_x2, bg_y2), bg_color, -1)
        
        # Draw text
        text_x = bg_x1 + padding
        text_y = bg_y1 + text_height + padding
        cv2.putText(result, title, (text_x, text_y), font, font_scale, color, thickness)
        
        # Add timestamp detail
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Timestamp text (smaller font)
        detail_font_scale = base_font_scale * 0.5
        detail_thickness = max(1, int(base_font_scale))
        (detail_width, detail_height), _ = cv2.getTextSize(timestamp, font, detail_font_scale, detail_thickness)
        
        detail_bg_x1 = padding
        detail_bg_y1 = bg_y2 + padding // 2
        detail_bg_x2 = detail_bg_x1 + detail_width + padding * 2
        detail_bg_y2 = detail_bg_y1 + detail_height + padding
        
        # Draw background for timestamp
        cv2.rectangle(result, (detail_bg_x1, detail_bg_y1), (detail_bg_x2, detail_bg_y2), bg_color, -1)
        
        # Draw timestamp
        detail_text_x = detail_bg_x1 + padding
        detail_text_y = detail_bg_y1 + detail_height + padding
        cv2.putText(result, timestamp, (detail_text_x, detail_text_y), font, 
                   detail_font_scale, color, detail_thickness)
        
        return result
    
    def create_field_background(self, color: Tuple[int, int, int] = (34, 139, 34)) -> np.ndarray:
        """
        สร้างพื้นหลังสนามฟุตบอล
        
        Args:
            color: สีสนาม (BGR format)
            
        Returns:
            Field background image
        """
        field = np.full((self.field_height, self.field_width, 3), color, dtype=np.uint8)
        
        # วาดเส้นสนาม (เส้นกลาง, วงกลมกลาง, กรอบ)
        line_color = (255, 255, 255)
        line_thickness = 3
        
        # เส้นกลาง
        cv2.line(field, (self.field_width // 2, 0), 
                (self.field_width // 2, self.field_height), line_color, line_thickness)
        
        # วงกลมกลาง
        center = (self.field_width // 2, self.field_height // 2)
        radius = min(self.field_width, self.field_height) // 6
        cv2.circle(field, center, radius, line_color, line_thickness)
        
        # กรอบสนาม
        cv2.rectangle(field, (0, 0), (self.field_width - 1, self.field_height - 1), 
                     line_color, line_thickness)
        
        return field

