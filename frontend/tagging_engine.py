"""
Tagging Engine - Professional tagging system for manual tracking
"""
import csv
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum

class EventType(Enum):
    """Event types for football tracking"""
    GOAL = "Goal"
    SHOT = "Shot"
    SHOT_ON_TARGET = "Shot on Target"
    SHOT_OFF_TARGET = "Shot off Target"
    PASS = "Pass"
    PASS_SUCCESS = "Pass Success"
    PASS_FAILED = "Pass Failed"
    TACKLE = "Tackle"
    TACKLE_SUCCESS = "Tackle Success"
    TACKLE_FAILED = "Tackle Failed"
    FOUL = "Foul"
    CORNER = "Corner"
    FREE_KICK = "Free Kick"
    YELLOW_CARD = "Yellow Card"
    RED_CARD = "Red Card"
    SUBSTITUTION = "Substitution"
    OFFSIDE = "Offside"
    SAVE = "Save"
    CROSS = "Cross"
    THROW_IN = "Throw In"
    PENALTY = "Penalty"

class Team(Enum):
    """Team options"""
    TEAM_A = "Team A"
    TEAM_B = "Team B"
    NEUTRAL = "Neutral"

@dataclass
class Tag:
    """Tag data structure"""
    id: str
    timestamp: float  # Time in seconds
    event_type: str
    team: str
    half: int = 1
    player_number: Optional[int] = None
    description: str = ""
    x_position: Optional[float] = None
    y_position: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)

class TaggingEngine:
    """Professional tagging engine for manual tracking"""
    
    def __init__(self):
        self.tags: List[Tag] = []
        self.video_path: Optional[str] = None
        self.match_name: str = "Match"
        self.team_a_name: str = "Team A"
        self.team_b_name: str = "Team B"
        self.match_date: Optional[str] = None
        self.next_tag_id: int = 1
    
    def create_tag(self, event_type: str, timestamp: float, team: str, 
                   half: int = 1, player_number: Optional[int] = None,
                   description: str = "", **metadata) -> Tag:
        """Create a new tag"""
        tag_id = f"TAG_{self.next_tag_id:04d}"
        self.next_tag_id += 1
        
        tag = Tag(
            id=tag_id,
            timestamp=timestamp,
            event_type=event_type,
            team=team,
            half=half,
            player_number=player_number,
            description=description,
            metadata=metadata
        )
        
        self.tags.append(tag)
        self._sort_tags()
        return tag
    
    def add_tag(self, tag: Tag):
        """Add an existing tag"""
        self.tags.append(tag)
        self._sort_tags()
    
    def remove_tag(self, tag_id: str) -> bool:
        """Remove tag by ID"""
        for i, tag in enumerate(self.tags):
            if tag.id == tag_id:
                self.tags.pop(i)
                return True
        return False
    
    def remove_tag_by_index(self, index: int) -> bool:
        """Remove tag by index"""
        if 0 <= index < len(self.tags):
            self.tags.pop(index)
            return True
        return False
    
    def get_tag(self, tag_id: str) -> Optional[Tag]:
        """Get tag by ID"""
        for tag in self.tags:
            if tag.id == tag_id:
                return tag
        return None
    
    def get_tags_by_type(self, event_type: str) -> List[Tag]:
        """Get all tags of a specific type"""
        return [tag for tag in self.tags if tag.event_type == event_type]
    
    def get_tags_by_team(self, team: str) -> List[Tag]:
        """Get all tags for a specific team"""
        return [tag for tag in self.tags if tag.team == team]
    
    def get_tags_by_half(self, half: int) -> List[Tag]:
        """Get all tags for a specific half"""
        return [tag for tag in self.tags if tag.half == half]
    
    def get_tags_in_range(self, start_time: float, end_time: float) -> List[Tag]:
        """Get all tags in time range"""
        return [tag for tag in self.tags if start_time <= tag.timestamp <= end_time]
    
    def _sort_tags(self):
        """Sort tags by timestamp"""
        self.tags.sort(key=lambda x: (x.half, x.timestamp))
    
    def clear_all_tags(self):
        """Clear all tags"""
        self.tags.clear()
        self.next_tag_id = 1
    
    def get_statistics(self) -> Dict:
        """Calculate comprehensive statistics"""
        stats = {
            'total_tags': len(self.tags),
            'tags_by_type': {},
            'tags_by_team': {'Team A': 0, 'Team B': 0, 'Neutral': 0},
            'tags_by_half': {1: 0, 2: 0},
            'goals': {'Team A': 0, 'Team B': 0},
            'shots': {'Team A': 0, 'Team B': 0, 'total': 0},
            'shots_on_target': {'Team A': 0, 'Team B': 0},
            'passes': {'Team A': 0, 'Team B': 0, 'total': 0},
            'passes_success': {'Team A': 0, 'Team B': 0},
            'tackles': {'Team A': 0, 'Team B': 0, 'total': 0},
            'tackles_success': {'Team A': 0, 'Team B': 0},
            'fouls': {'Team A': 0, 'Team B': 0},
            'cards': {'Team A': {'yellow': 0, 'red': 0}, 'Team B': {'yellow': 0, 'red': 0}},
            'corners': {'Team A': 0, 'Team B': 0},
            'offsides': {'Team A': 0, 'Team B': 0},
        }
        
        for tag in self.tags:
            # Count by type
            if tag.event_type not in stats['tags_by_type']:
                stats['tags_by_type'][tag.event_type] = 0
            stats['tags_by_type'][tag.event_type] += 1
            
            # Count by team
            if tag.team in stats['tags_by_team']:
                stats['tags_by_team'][tag.team] += 1
            
            # Count by half
            if tag.half in stats['tags_by_half']:
                stats['tags_by_half'][tag.half] += 1
            
            # Specific event counts
            if tag.event_type == EventType.GOAL.value:
                if tag.team in stats['goals']:
                    stats['goals'][tag.team] += 1
            elif tag.event_type == EventType.SHOT.value:
                if tag.team in stats['shots']:
                    stats['shots'][tag.team] += 1
                    stats['shots']['total'] += 1
            elif tag.event_type == EventType.SHOT_ON_TARGET.value:
                if tag.team in stats['shots_on_target']:
                    stats['shots_on_target'][tag.team] += 1
            elif tag.event_type == EventType.PASS.value:
                if tag.team in stats['passes']:
                    stats['passes'][tag.team] += 1
                    stats['passes']['total'] += 1
            elif tag.event_type == EventType.PASS_SUCCESS.value:
                if tag.team in stats['passes_success']:
                    stats['passes_success'][tag.team] += 1
            elif tag.event_type == EventType.TACKLE.value:
                if tag.team in stats['tackles']:
                    stats['tackles'][tag.team] += 1
                    stats['tackles']['total'] += 1
            elif tag.event_type == EventType.TACKLE_SUCCESS.value:
                if tag.team in stats['tackles_success']:
                    stats['tackles_success'][tag.team] += 1
            elif tag.event_type == EventType.FOUL.value:
                if tag.team in stats['fouls']:
                    stats['fouls'][tag.team] += 1
            elif tag.event_type == EventType.YELLOW_CARD.value:
                if tag.team in stats['cards']:
                    stats['cards'][tag.team]['yellow'] += 1
            elif tag.event_type == EventType.RED_CARD.value:
                if tag.team in stats['cards']:
                    stats['cards'][tag.team]['red'] += 1
            elif tag.event_type == EventType.CORNER.value:
                if tag.team in stats['corners']:
                    stats['corners'][tag.team] += 1
            elif tag.event_type == EventType.OFFSIDE.value:
                if tag.team in stats['offsides']:
                    stats['offsides'][tag.team] += 1
        
        return stats
    
    def export_to_csv(self, filepath: str):
        """Export tags to CSV file"""
        if not self.tags:
            raise ValueError("No tags to export")
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['id', 'timestamp', 'time_formatted', 'event_type', 'team', 
                          'half', 'player_number', 'description', 'x_position', 'y_position']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for tag in self.tags:
                minutes = int(tag.timestamp // 60)
                seconds = int(tag.timestamp % 60)
                time_formatted = f"{minutes:02d}:{seconds:02d}"
                
                writer.writerow({
                    'id': tag.id,
                    'timestamp': tag.timestamp,
                    'time_formatted': time_formatted,
                    'event_type': tag.event_type,
                    'team': tag.team,
                    'half': tag.half,
                    'player_number': tag.player_number or '',
                    'description': tag.description,
                    'x_position': tag.x_position or '',
                    'y_position': tag.y_position or ''
                })
    
    def export_to_json(self, filepath: str):
        """Export tags to JSON file"""
        data = {
            'match_info': {
                'match_name': self.match_name,
                'team_a': self.team_a_name,
                'team_b': self.team_b_name,
                'match_date': self.match_date,
                'video_path': self.video_path
            },
            'tags': [tag.to_dict() for tag in self.tags],
            'statistics': self.get_statistics()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def import_from_csv(self, filepath: str):
        """Import tags from CSV file"""
        self.clear_all_tags()
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                tag = Tag(
                    id=row.get('id', f"TAG_{self.next_tag_id:04d}"),
                    timestamp=float(row.get('timestamp', 0)),
                    event_type=row.get('event_type', ''),
                    team=row.get('team', 'Neutral'),
                    half=int(row.get('half', 1)),
                    player_number=int(row['player_number']) if row.get('player_number') else None,
                    description=row.get('description', ''),
                    x_position=float(row['x_position']) if row.get('x_position') else None,
                    y_position=float(row['y_position']) if row.get('y_position') else None
                )
                self.add_tag(tag)
                self.next_tag_id = max(self.next_tag_id, int(tag.id.split('_')[1]) + 1 if '_' in tag.id else self.next_tag_id)

