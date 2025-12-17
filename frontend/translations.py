"""
Translation System for FREE Football Analysis
Loads translations from Excel file (translations.xlsx)
Format: Column A = Thai (TH), Column B = English (EN)
"""
import os
import sys
from typing import Dict, Optional
from pathlib import Path

# Get project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TRANSLATIONS_FILE = os.path.join(PROJECT_ROOT, "translations.xlsx")

class TranslationManager:
    """Manages translations loaded from Excel file"""
    
    def __init__(self):
        self.translations: Dict[str, Dict[str, str]] = {}  # {key: {th: "...", en: "..."}}
        self.current_language = "TH"  # Default to Thai
        self._load_translations()
    
    def _load_translations(self):
        """Load translations from Excel file"""
        try:
            import pandas as pd
            
            if not os.path.exists(TRANSLATIONS_FILE):
                # Create default translations file if it doesn't exist
                self._create_default_translations_file()
                return
            
            # Read Excel file
            df = pd.read_excel(TRANSLATIONS_FILE, sheet_name=0)
            
            # Expected format: Column A = Key/Thai, Column B = English
            # Or: Column A = Key, Column B = Thai, Column C = English
            if len(df.columns) >= 2:
                # Try different formats
                if 'Key' in df.columns or 'key' in df.columns:
                    # Format: Key | Thai | English
                    key_col = 'Key' if 'Key' in df.columns else 'key'
                    th_col = 'Thai' if 'Thai' in df.columns else 'thai' if 'thai' in df.columns else df.columns[1]
                    en_col = 'English' if 'English' in df.columns else 'english' if 'english' in df.columns else df.columns[2] if len(df.columns) > 2 else df.columns[1]
                    
                    for _, row in df.iterrows():
                        key = str(row[key_col]).strip()
                        th = str(row[th_col]).strip() if pd.notna(row[th_col]) else key
                        en = str(row[en_col]).strip() if pd.notna(row[en_col]) and len(df.columns) > 2 else th
                        
                        if key and key != 'nan':
                            self.translations[key] = {'TH': th, 'EN': en}
                else:
                    # Format: Thai | English (use Thai as key)
                    th_col = df.columns[0]
                    en_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
                    
                    for _, row in df.iterrows():
                        th = str(row[th_col]).strip() if pd.notna(row[th_col]) else ""
                        en = str(row[en_col]).strip() if pd.notna(row[en_col]) else th
                        
                        if th:
                            self.translations[th] = {'TH': th, 'EN': en}
            
        except ImportError:
            print("Warning: pandas not available. Translations will not work.")
        except Exception as e:
            print(f"Warning: Could not load translations: {e}")
            # Create default file
            self._create_default_translations_file()
    
    def _create_default_translations_file(self):
        """Create default translations Excel file"""
        try:
            import pandas as pd
            
            # Default translations
            default_translations = [
                # UI Labels
                {'Key': 'version', 'Thai': 'เวอร์ชัน:', 'English': 'Version:'},
                {'Key': 'build', 'Thai': 'Build:', 'English': 'Build:'},
                {'Key': 'developer', 'Thai': 'ผู้พัฒนา:', 'English': 'Developer:'},
                {'Key': 'language', 'Thai': 'ภาษา', 'English': 'Language'},
                {'Key': 'thai', 'Thai': 'ไทย', 'English': 'Thai'},
                {'Key': 'english', 'Thai': 'อังกฤษ', 'English': 'English'},
                
                # Buttons and Actions
                {'Key': 'start_analysis', 'Thai': 'เริ่มวิเคราะห์ (Start Analysis)', 'English': 'Start Analysis'},
                {'Key': 'processing_video', 'Thai': 'กำลังประมวลผลวิดีโอ...', 'English': 'Processing video...'},
                {'Key': 'processing_complete', 'Thai': 'ประมวลผลเสร็จสิ้น!', 'English': 'Processing complete!'},
                {'Key': 'error_occurred', 'Thai': 'เกิดข้อผิดพลาด:', 'English': 'Error occurred:'},
                {'Key': 'no_data', 'Thai': 'ไม่มีข้อมูล', 'English': 'No data'},
                {'Key': 'success', 'Thai': 'สำเร็จ', 'English': 'Success'},
                {'Key': 'failed', 'Thai': 'ไม่สำเร็จ', 'English': 'Failed'},
                
                # Manual Tracking
                {'Key': 'export_tracking', 'Thai': 'ส่งออกข้อมูลการติดตาม', 'English': 'Export Tracking Data'},
                {'Key': 'no_tracking_data', 'Thai': 'ไม่มีเหตุการณ์ที่ติดตามเพื่อส่งออก', 'English': 'No tracking events to export'},
                {'Key': 'export_success', 'Thai': 'ส่งออกข้อมูลการติดตามไปยัง:', 'English': 'Tracking data exported to:'},
                {'Key': 'raw_data', 'Thai': 'ข้อมูลดิบ', 'English': 'Raw Data'},
                {'Key': 'summary', 'Thai': 'สรุปผลรวม', 'English': 'Summary'},
                {'Key': 'team_comparison', 'Thai': 'เปรียบเทียบทีม', 'English': 'Team Comparison'},
                {'Key': 'player_list', 'Thai': 'รายชื่อนักเตะ', 'English': 'Player List'},
                {'Key': 'goals_summary', 'Thai': 'สรุปประตู', 'English': 'Goals Summary'},
                {'Key': 'first_half', 'Thai': 'ครึ่งแรก', 'English': 'First Half'},
                {'Key': 'second_half', 'Thai': 'ครึ่งหลัง', 'English': 'Second Half'},
                {'Key': 'extra_time_first', 'Thai': 'ต่อเวลาครึ่งแรก', 'English': 'Extra Time First Half'},
                {'Key': 'extra_time_second', 'Thai': 'ต่อเวลาครึ่งหลัง', 'English': 'Extra Time Second Half'},
                {'Key': 'timeline', 'Thai': 'ไทม์ไลน์', 'English': 'Timeline'},
                {'Key': 'key_moments', 'Thai': 'ช่วงเวลาสำคัญ', 'English': 'Key Moments'},
                {'Key': 'event_frequency', 'Thai': 'ความถี่เหตุการณ์', 'English': 'Event Frequency'},
                {'Key': 'set_pieces', 'Thai': 'ลูกตั้งเตะ', 'English': 'Set Pieces'},
                {'Key': 'player_stats', 'Thai': 'สถิติผู้เล่น', 'English': 'Player Statistics'},
                {'Key': 'analysis_stats', 'Thai': 'สถิติการวิเคราะห์', 'English': 'Analysis Statistics'},
                
                # Event Types
                # Event Types - Actions
                {'Key': 'ยิง', 'Thai': 'ยิง', 'English': 'Shot'},
                {'Key': 'ส่งบอล', 'Thai': 'ส่งบอล', 'English': 'Pass'},
                {'Key': 'ข้ามบอล', 'Thai': 'ข้ามบอล', 'English': 'Cross'},
                {'Key': 'ผ่านบอล', 'Thai': 'ผ่านบอล', 'English': 'Through Ball'},
                {'Key': 'ส่งบอลยาว', 'Thai': 'ส่งบอลยาว', 'English': 'Long Pass'},
                {'Key': 'ส่งบอลสั้น', 'Thai': 'ส่งบอลสั้น', 'English': 'Short Pass'},
                {'Key': 'ส่งบอลในเขตโทษ', 'Thai': 'ส่งบอลในเขตโทษ', 'English': 'Pass in Penalty Area'},
                {'Key': 'เตะมุม', 'Thai': 'เตะมุม', 'English': 'Corner Kick'},
                {'Key': 'ฟรีคิก', 'Thai': 'ฟรีคิก', 'English': 'Free Kick'},
                {'Key': 'ลูกโทษ', 'Thai': 'ลูกโทษ', 'English': 'Penalty'},
                {'Key': 'ทุ่มบอล', 'Thai': 'ทุ่มบอล', 'English': 'Throw In'},
                {'Key': 'แย่งบอล', 'Thai': 'แย่งบอล', 'English': 'Tackle'},
                {'Key': 'สกัดบอล', 'Thai': 'สกัดบอล', 'English': 'Interception'},
                {'Key': 'เคลียร์บอล', 'Thai': 'เคลียร์บอล', 'English': 'Clearance'},
                {'Key': 'บล็อก', 'Thai': 'บล็อก', 'English': 'Block'},
                {'Key': 'เซฟ', 'Thai': 'เซฟ', 'English': 'Save'},
                {'Key': 'ฟาวล์', 'Thai': 'ฟาวล์', 'English': 'Foul'},
                {'Key': 'ใบเหลือง', 'Thai': 'ใบเหลือง', 'English': 'Yellow Card'},
                {'Key': 'ใบแดง', 'Thai': 'ใบแดง', 'English': 'Red Card'},
                {'Key': 'ออฟไซด์', 'Thai': 'ออฟไซด์', 'English': 'Offside'},
                {'Key': 'บอลออก', 'Thai': 'บอลออก', 'English': 'Ball Out'},
                {'Key': 'เปลี่ยนตัว', 'Thai': 'เปลี่ยนตัว', 'English': 'Substitution'},
                {'Key': 'บาดเจ็บ', 'Thai': 'บาดเจ็บ', 'English': 'Injury'},
                {'Key': 'เสียบอล', 'Thai': 'เสียบอล', 'English': 'Lost Ball'},
                {'Key': 'ครองบอล', 'Thai': 'ครองบอล', 'English': 'Ball Possession'},
                
                # Legacy keys for backward compatibility
                {'Key': 'goal', 'Thai': 'ประตู', 'English': 'Goal'},
                {'Key': 'shot', 'Thai': 'ยิง', 'English': 'Shot'},
                {'Key': 'pass', 'Thai': 'ส่งบอล', 'English': 'Pass'},
                {'Key': 'cross', 'Thai': 'ข้ามบอล', 'English': 'Cross'},
                {'Key': 'through_ball', 'Thai': 'ผ่านบอล', 'English': 'Through Ball'},
                {'Key': 'long_pass', 'Thai': 'ส่งบอลยาว', 'English': 'Long Pass'},
                {'Key': 'short_pass', 'Thai': 'ส่งบอลสั้น', 'English': 'Short Pass'},
                {'Key': 'pass_in_box', 'Thai': 'ส่งบอลในเขตโทษ', 'English': 'Pass in Box'},
                {'Key': 'throw_in', 'Thai': 'ทุ่มบอล', 'English': 'Throw In'},
                {'Key': 'tackle', 'Thai': 'แย่งบอล', 'English': 'Tackle'},
                {'Key': 'interception', 'Thai': 'สกัดบอล', 'English': 'Interception'},
                {'Key': 'clearance', 'Thai': 'เคลียร์บอล', 'English': 'Clearance'},
                {'Key': 'block', 'Thai': 'บล็อก', 'English': 'Block'},
                {'Key': 'save', 'Thai': 'เซฟ', 'English': 'Save'},
                {'Key': 'foul', 'Thai': 'ฟาวล์', 'English': 'Foul'},
                {'Key': 'yellow_card', 'Thai': 'ใบเหลือง', 'English': 'Yellow Card'},
                {'Key': 'red_card', 'Thai': 'ใบแดง', 'English': 'Red Card'},
                {'Key': 'offside', 'Thai': 'ออฟไซด์', 'English': 'Offside'},
                {'Key': 'ball_out', 'Thai': 'บอลออก', 'English': 'Ball Out'},
                {'Key': 'substitution', 'Thai': 'เปลี่ยนตัว', 'English': 'Substitution'},
                {'Key': 'injury', 'Thai': 'บาดเจ็บ', 'English': 'Injury'},
                {'Key': 'ball_lost', 'Thai': 'เสียบอล', 'English': 'Ball Lost'},
                {'Key': 'possession', 'Thai': 'ครองบอล', 'English': 'Possession'},
                {'Key': 'corner', 'Thai': 'เตะมุม', 'English': 'Corner'},
                {'Key': 'free_kick', 'Thai': 'ฟรีคิก', 'English': 'Free Kick'},
                {'Key': 'penalty', 'Thai': 'ลูกโทษ', 'English': 'Penalty'},
                
                # Outcomes - All possible outcomes
                # Outcomes
                {'Key': 'ประตู', 'Thai': 'ประตู', 'English': 'Goal'},
                {'Key': 'ยิงเข้า', 'Thai': 'ยิงเข้า', 'English': 'Shot on Target'},
                {'Key': 'ยิงออก', 'Thai': 'ยิงออก', 'English': 'Shot off Target'},
                {'Key': 'บล็อก', 'Thai': 'บล็อก', 'English': 'Blocked'},
                {'Key': 'ถูกเซฟ', 'Thai': 'ถูกเซฟ', 'English': 'Saved'},
                {'Key': 'สำเร็จ', 'Thai': 'สำเร็จ', 'English': 'Success'},
                {'Key': 'ไม่สำเร็จ', 'Thai': 'ไม่สำเร็จ', 'English': 'Failed'},
                {'Key': 'แอสซิสต์', 'Thai': 'แอสซิสต์', 'English': 'Assist'},
                {'Key': 'คีย์พาส', 'Thai': 'คีย์พาส', 'English': 'Key Pass'},
                {'Key': 'ไม่ประตู', 'Thai': 'ไม่ประตู', 'English': 'No Goal'},
                {'Key': 'เคลียร์', 'Thai': 'เคลียร์', 'English': 'Cleared'},
                {'Key': 'อันตราย', 'Thai': 'อันตราย', 'English': 'Dangerous'},
                {'Key': 'บล็อกยิง', 'Thai': 'บล็อกยิง', 'English': 'Block Shot'},
                {'Key': 'เซฟ', 'Thai': 'เซฟ', 'English': 'Save'},
                {'Key': 'ไม่เซฟ', 'Thai': 'ไม่เซฟ', 'English': 'No Save'},
                {'Key': 'เซฟสำคัญ', 'Thai': 'เซฟสำคัญ', 'English': 'Important Save'},
                {'Key': 'ฟาวล์', 'Thai': 'ฟาวล์', 'English': 'Foul'},
                {'Key': 'ใบเหลือง', 'Thai': 'ใบเหลือง', 'English': 'Yellow Card'},
                {'Key': 'ใบแดง', 'Thai': 'ใบแดง', 'English': 'Red Card'},
                {'Key': 'ออฟไซด์', 'Thai': 'ออฟไซด์', 'English': 'Offside'},
                {'Key': 'บอลออก', 'Thai': 'บอลออก', 'English': 'Ball Out'},
                {'Key': 'เปลี่ยนตัวเข้า', 'Thai': 'เปลี่ยนตัวเข้า', 'English': 'Substitution In'},
                {'Key': 'เปลี่ยนตัวออก', 'Thai': 'เปลี่ยนตัวออก', 'English': 'Substitution Out'},
                {'Key': 'บาดเจ็บ', 'Thai': 'บาดเจ็บ', 'English': 'Injury'},
                {'Key': 'เสียบอล', 'Thai': 'เสียบอล', 'English': 'Lost Ball'},
                {'Key': 'ครองบอล', 'Thai': 'ครองบอล', 'English': 'Ball Possession'},
                
                # Legacy keys for backward compatibility
                {'Key': 'goal', 'Thai': 'ประตู', 'English': 'Goal'},
                {'Key': 'shot_on_target', 'Thai': 'ยิงเข้า', 'English': 'Shot on Target'},
                {'Key': 'shot_off_target', 'Thai': 'ยิงออก', 'English': 'Shot off Target'},
                {'Key': 'saved', 'Thai': 'ถูกเซฟ', 'English': 'Saved'},
                {'Key': 'assist', 'Thai': 'แอสซิสต์', 'English': 'Assist'},
                {'Key': 'key_pass', 'Thai': 'คีย์พาส', 'English': 'Key Pass'},
                {'Key': 'blocked', 'Thai': 'บล็อก', 'English': 'Blocked'},
                {'Key': 'no_goal', 'Thai': 'ไม่ประตู', 'English': 'No Goal'},
                {'Key': 'success', 'Thai': 'สำเร็จ', 'English': 'Success'},
                {'Key': 'failed', 'Thai': 'ไม่สำเร็จ', 'English': 'Failed'},
                {'Key': 'dangerous', 'Thai': 'อันตราย', 'English': 'Dangerous'},
                {'Key': 'block_shot', 'Thai': 'บล็อกยิง', 'English': 'Block Shot'},
                {'Key': 'important_save', 'Thai': 'เซฟสำคัญ', 'English': 'Important Save'},
                {'Key': 'no_save', 'Thai': 'ไม่เซฟ', 'English': 'No Save'},
                {'Key': 'substitution_in', 'Thai': 'เปลี่ยนตัวเข้า', 'English': 'Substitution In'},
                {'Key': 'substitution_out', 'Thai': 'เปลี่ยนตัวออก', 'English': 'Substitution Out'},
                {'Key': 'clear', 'Thai': 'เคลียร์', 'English': 'Clear'},
                {'Key': 'no_result', 'Thai': 'ไม่มีผลลัพธ์', 'English': 'No Result'},
                {'Key': 'not_specified', 'Thai': 'ไม่ระบุ', 'English': 'Not Specified'},
                
                # Excel Column Headers
                {'Key': 'time', 'Thai': 'เวลา', 'English': 'Time'},
                {'Key': 'time_seconds', 'Thai': 'เวลา (วินาที)', 'English': 'Time (seconds)'},
                {'Key': 'event', 'Thai': 'เหตุการณ์', 'English': 'Event'},
                {'Key': 'outcome', 'Thai': 'ผลลัพธ์', 'English': 'Outcome'},
                {'Key': 'team', 'Thai': 'ทีม', 'English': 'Team'},
                {'Key': 'half_text', 'Thai': 'ครึ่ง (ข้อความ)', 'English': 'Half (text)'},
                {'Key': 'half_number', 'Thai': 'ครึ่ง (ตัวเลข)', 'English': 'Half (number)'},
                {'Key': 'player_number', 'Thai': 'หมายเลขผู้เล่น', 'English': 'Player Number'},
                {'Key': 'player_name', 'Thai': 'ชื่อผู้เล่น', 'English': 'Player Name'},
                {'Key': 'description', 'Thai': 'คำอธิบาย', 'English': 'Description'},
                {'Key': 'position_x', 'Thai': 'ตำแหน่ง X', 'English': 'Position X'},
                {'Key': 'position_y', 'Thai': 'ตำแหน่ง Y', 'English': 'Position Y'},
                {'Key': 'half', 'Thai': 'ครึ่ง', 'English': 'Half'},
                {'Key': 'minute', 'Thai': 'นาที', 'English': 'Minute'},
                {'Key': 'type', 'Thai': 'ประเภท', 'English': 'Type'},
                {'Key': 'scorer', 'Thai': 'ผู้ยิง', 'English': 'Scorer'},
                {'Key': 'order', 'Thai': 'ลำดับ', 'English': 'Order'},
                
                # Statistics
                {'Key': 'category', 'Thai': 'หมวดหมู่', 'English': 'Category'},
                {'Key': 'item', 'Thai': 'รายการ', 'English': 'Item'},
                {'Key': 'count', 'Thai': 'จำนวน', 'English': 'Count'},
                {'Key': 'note', 'Thai': 'หมายเหตุ', 'English': 'Note'},
                {'Key': 'variable', 'Thai': 'ตัวแปร', 'English': 'Variable'},
                {'Key': 'difference', 'Thai': 'ความแตกต่าง', 'English': 'Difference'},
                {'Key': 'team_with_more', 'Thai': 'ทีมที่มากกว่า', 'English': 'Team with More'},
                {'Key': 'equal', 'Thai': 'เท่ากัน', 'English': 'Equal'},
                {'Key': 'percentage', 'Thai': 'เปอร์เซ็นต์ (%)', 'English': 'Percentage (%)'},
                
                # More statistics labels
                {'Key': 'overview', 'Thai': 'ภาพรวม', 'English': 'Overview'},
                {'Key': 'total_events', 'Thai': 'จำนวนเหตุการณ์ทั้งหมด', 'English': 'Total Events'},
                {'Key': 'teams_analyzed', 'Thai': 'จำนวนทีมที่วิเคราะห์', 'English': 'Teams Analyzed'},
                {'Key': 'event_type', 'Thai': 'ประเภทเหตุการณ์', 'English': 'Event Type'},
                {'Key': 'team_summary', 'Thai': 'สรุปตามทีม', 'English': 'Team Summary'},
                {'Key': 'time_stats', 'Thai': 'สถิติเวลา', 'English': 'Time Statistics'},
                {'Key': 'half_stats', 'Thai': 'สถิติตามครึ่ง', 'English': 'Half Statistics'},
                {'Key': 'success_rate', 'Thai': 'อัตราความสำเร็จ', 'English': 'Success Rate'},
                {'Key': 'from_total', 'Thai': 'จากทั้งหมด', 'English': 'From Total'},
                {'Key': 'team_events', 'Thai': 'เหตุการณ์ของทีม', 'English': 'Team Events'},
                
                # AI - Tracking Tab
                {'Key': 'display_options', 'Thai': 'ตัวเลือกการแสดงผล', 'English': 'Display Options'},
                {'Key': 'track_players', 'Thai': 'Track ผู้เล่น', 'English': 'Track Players'},
                {'Key': 'track_goalkeepers', 'Thai': 'Track ผู้รักษาประตู', 'English': 'Track Goalkeepers'},
                {'Key': 'track_referees', 'Thai': 'Track ผู้ตัดสิน', 'English': 'Track Referees'},
                {'Key': 'track_ball', 'Thai': 'Track ลูกบอล', 'English': 'Track Ball'},
                {'Key': 'show_statistics', 'Thai': 'แสดงสถิติ', 'English': 'Show Statistics'},
                {'Key': 'display_options_note', 'Thai': '💡 หมายเหตุ: ตัวเลือกข้างต้นใช้สำหรับการแสดงผลในวิดีโอเท่านั้น ไม่ส่งผลต่อการวิเคราะห์ผลด้าน ImageProcessing ของ AI', 'English': '💡 Note: The above options are for video display only and do not affect AI ImageProcessing analysis results'},
                {'Key': 'demo', 'Thai': 'ตัวอย่าง', 'English': 'Demo'},
                {'Key': 'demo_instruction', 'Thai': 'เลือกวิดีโอตัวอย่างจาก 2 วิดีโอ', 'English': 'Select demo video from 2 videos'},
                {'Key': 'demo1', 'Thai': 'ตัวอย่าง 1', 'English': 'Demo 1'},
                {'Key': 'demo2', 'Thai': 'ตัวอย่าง 2', 'English': 'Demo 2'},
                {'Key': 'upload_video', 'Thai': 'อัปโหลดวิดีโอ', 'English': 'Upload Video'},
                {'Key': 'select_video_file', 'Thai': 'เลือกไฟล์วิดีโอ', 'English': 'Select Video File'},
                {'Key': 'start_analysis', 'Thai': 'เริ่มวิเคราะห์', 'English': 'Start Analysis'},
                
                # Video Preview
                {'Key': 'open_video', 'Thai': 'เปิดวีดีโอ', 'English': 'Open Video'},
                {'Key': 'open_output_folder', 'Thai': 'เปิดโฟลเดอร์ผลลัพธ์', 'English': 'Open Output Folder'},
                {'Key': 'speed', 'Thai': 'ความเร็ว:', 'English': 'Speed:'},
                
                # Heat Map
                {'Key': 'heat_maps_info', 'Thai': 'Heat Maps จะแสดงผลหลังจากกดวิเคราะห์วิดีโอ', 'English': 'Heat Maps will be displayed after analyzing video'},
                {'Key': 'select_heat_map_type', 'Thai': 'เลือกประเภท Heat Map', 'English': 'Select Heat Map Type'},
                {'Key': 'save_heat_map_png', 'Thai': 'บันทึก Heat Map เป็น PNG', 'English': 'Save Heat Map as PNG'},
                {'Key': 'all_players', 'Thai': 'ผู้เล่นทั้งหมด', 'English': 'All Players'},
                {'Key': 'ball', 'Thai': 'ลูกบอล', 'English': 'Ball'},
                
                # Statistics
                {'Key': 'statistics', 'Thai': 'Statistics', 'English': 'Statistics'},
                {'Key': 'statistics_info', 'Thai': 'สถิติจะแสดงผลหลังจากกดวิเคราะห์วิดีโอ', 'English': 'Statistics will be displayed after analyzing video'},
                {'Key': 'team_statistics', 'Thai': 'Team Statistics', 'English': 'Team Statistics'},
                {'Key': 'no_statistics_data', 'Thai': 'ยังไม่มีข้อมูลสถิติ\nกรุณากดวิเคราะห์วิดีโอก่อน', 'English': 'No statistics data yet\nPlease analyze video first'},
                {'Key': 'no_player_data', 'Thai': 'ยังไม่มีข้อมูลผู้เล่น\nกรุณากดวิเคราะห์วิดีโอก่อน', 'English': 'No player data yet\nPlease analyze video first'},
                {'Key': 'team', 'Thai': 'ทีม', 'English': 'Team'},
                {'Key': 'ball_possession', 'Thai': 'ครองบอล:', 'English': 'Ball Possession:'},
                {'Key': 'possession_time', 'Thai': 'เวลาครองบอล:', 'English': 'Possession Time:'},
                {'Key': 'possession_frames', 'Thai': 'เฟรมครองบอล:', 'English': 'Possession Frames:'},
                {'Key': 'total_touches', 'Thai': 'การสัมผัสบอลทั้งหมด:', 'English': 'Total Touches:'},
                {'Key': 'players_detected', 'Thai': 'จำนวนผู้เล่นที่ตรวจจับได้:', 'English': 'Players Detected:'},
                {'Key': 'active_frames', 'Thai': 'เฟรมที่ใช้งาน:', 'English': 'Active Frames:'},
                {'Key': 'minutes', 'Thai': 'นาที', 'English': 'minutes'},
                {'Key': 'frames', 'Thai': 'เฟรม', 'English': 'frames'},
                {'Key': 'overall_statistics', 'Thai': 'สถิติรวม', 'English': 'Overall Statistics'},
                {'Key': 'no_image', 'Thai': 'ไม่มีรูปภาพ', 'English': 'No Image'},
                {'Key': 'total_frames', 'Thai': 'เฟรมทั้งหมด:', 'English': 'Total Frames:'},
                {'Key': 'video_duration', 'Thai': 'ระยะเวลาวิดีโอ:', 'English': 'Video Duration:'},
                {'Key': 'players', 'Thai': 'ผู้เล่น', 'English': 'Players'},
                {'Key': 'total_possession_frames', 'Thai': 'เฟรมครองบอลทั้งหมด:', 'English': 'Total Possession Frames:'},
                
                # Movement Analysis
                {'Key': 'movement_analysis_info', 'Thai': 'วิเคราะห์การเคลื่อนไหวจะแสดงผลหลังจากกดวิเคราะห์วิดีโอ', 'English': 'Movement analysis will be displayed after analyzing video'},
                {'Key': 'analysis_type', 'Thai': 'ประเภทการวิเคราะห์', 'English': 'Analysis Type'},
                {'Key': 'select_team_player', 'Thai': 'เลือกทีม/ผู้เล่น', 'English': 'Select Team/Player'},
                {'Key': 'movement_paths', 'Thai': 'เส้นทางการเคลื่อนที่', 'English': 'Movement Paths'},
                {'Key': 'speed_zones', 'Thai': 'Speed Zones (พื้นที่ความเร็วสูง)', 'English': 'Speed Zones (High Speed Areas)'},
                {'Key': 'speed_chart', 'Thai': 'กราฟความเร็ว', 'English': 'Speed Chart'},
                {'Key': 'movement_statistics', 'Thai': 'สถิติการเคลื่อนไหว', 'English': 'Movement Statistics'},
                {'Key': 'no_movement_data', 'Thai': 'ยังไม่มีข้อมูลการวิเคราะห์การเคลื่อนไหว\nกรุณากดวิเคราะห์วิดีโอก่อน', 'English': 'No movement analysis data yet\nPlease analyze video first'},
                {'Key': 'save_analysis_image', 'Thai': 'บันทึกภาพวิเคราะห์', 'English': 'Save Analysis Image'},
                {'Key': 'movement_stats_title', 'Thai': '=== สถิติการเคลื่อนไหว ===', 'English': '=== Movement Statistics ==='},
                {'Key': 'number_of_players', 'Thai': 'จำนวนผู้เล่น:', 'English': 'Number of Players:'},
                {'Key': 'total_distance', 'Thai': 'ระยะทางรวม:', 'English': 'Total Distance:'},
                {'Key': 'distance', 'Thai': 'ระยะทาง:', 'English': 'Distance:'},
                {'Key': 'average_speed', 'Thai': 'ความเร็วเฉลี่ย:', 'English': 'Average Speed:'},
                {'Key': 'maximum_speed', 'Thai': 'ความเร็วสูงสุด:', 'English': 'Maximum Speed:'},
                {'Key': 'minimum_speed', 'Thai': 'ความเร็วต่ำสุด:', 'English': 'Minimum Speed:'},
                {'Key': 'play_time', 'Thai': 'เวลาเล่น:', 'English': 'Play Time:'},
                {'Key': 'seconds', 'Thai': 'วินาที', 'English': 'seconds'},
                {'Key': 'average_speed_over_time', 'Thai': 'Average Speed Over Time', 'English': 'Average Speed Over Time'},
                {'Key': 'no_speed_data', 'Thai': 'ไม่มีข้อมูลความเร็ว', 'English': 'No speed data'},
                {'Key': 'no_speed_data_threshold', 'Thai': 'ไม่มีข้อมูลความเร็วสูงกว่า', 'English': 'No data with speed higher than'},
                
                # Logs
                {'Key': 'tracking_log', 'Thai': 'Tracking Log', 'English': 'Tracking Log'},
                {'Key': 'camera_movement_log', 'Thai': 'Camera Movement Log', 'English': 'Camera Movement Log'},
                {'Key': 'memory_access_log', 'Thai': 'Memory Access Log', 'English': 'Memory Access Log'},
                
                # AI Results Sub-tabs
                {'Key': 'heat_map', 'Thai': 'Heat Map', 'English': 'Heat Map'},
                {'Key': 'statistics', 'Thai': 'Statistics', 'English': 'Statistics'},
                {'Key': 'movement_analysis', 'Thai': 'Movement Analysis', 'English': 'Movement Analysis'},
                {'Key': 'pass_analysis', 'Thai': 'Pass Analysis', 'English': 'Pass Analysis'},
                {'Key': 'zone_analysis', 'Thai': 'Zone Analysis', 'English': 'Zone Analysis'},
                
                # Pass Analysis
                {'Key': 'pass_analysis_coming_soon', 'Thai': 'การวิเคราะห์การส่งบอล\nเร็วๆ นี้', 'English': 'Pass Analysis\nComing Soon'},
                {'Key': 'pass_analysis_description', 'Thai': 'แท็บนี้จะแสดง:\n• อัตราความสำเร็จในการส่งบอล\n• การวิเคราะห์ระยะทางการส่งบอล\n• Heat Map ทิศทางการส่งบอล\n• การระบุการส่งบอลสำคัญ\n• ห่วงโซ่การส่งบอล\n• และอื่นๆ...', 'English': 'This tab will show:\n• Pass success rate\n• Pass distance analysis\n• Pass direction heat map\n• Key passes identification\n• Pass chains\n• And more...'},
                
                # Zone Analysis
                {'Key': 'zone_analysis_coming_soon', 'Thai': 'การวิเคราะห์โซน\nเร็วๆ นี้', 'English': 'Zone Analysis\nComing Soon'},
                {'Key': 'zone_analysis_description', 'Thai': 'แท็บนี้จะแสดง:\n• กิจกรรมตามโซนสนาม\n• การวิเคราะห์โซนป้องกัน\n• การวิเคราะห์โซนกลาง\n• การวิเคราะห์โซนบุก\n• สถิติตามโซน\n• และอื่นๆ...', 'English': 'This tab will show:\n• Activity by field zones\n• Defensive third analysis\n• Middle third analysis\n• Attacking third analysis\n• Zone-based statistics\n• And more...'},
            ]
            
            df = pd.DataFrame(default_translations)
            df.to_excel(TRANSLATIONS_FILE, index=False, sheet_name='Translations')
            print(f"Created default translations file: {TRANSLATIONS_FILE}")
            
            # Load the created file
            self._load_translations()
            
        except ImportError:
            print("Warning: pandas not available. Cannot create translations file.")
        except Exception as e:
            print(f"Warning: Could not create translations file: {e}")
    
    def set_language(self, lang: str):
        """Set current language (TH or EN)"""
        if lang.upper() in ['TH', 'EN']:
            self.current_language = lang.upper()
    
    def get_language(self) -> str:
        """Get current language"""
        return self.current_language
    
    def translate(self, text: str, default: Optional[str] = None) -> str:
        """
        Translate text to current language
        If text is not found in translations, returns original text or default
        """
        if not text:
            return text or default or ""
        
        # Check if we have translation for this text (using Thai text as key)
        if text in self.translations:
            trans = self.translations[text]
            result = trans.get(self.current_language, text)
            # If current language is not in translations, try to return the other language
            if result == text and self.current_language == 'EN' and 'EN' in trans:
                return trans.get('EN', default if default is not None else text)
            elif result == text and self.current_language == 'TH' and 'TH' in trans:
                return trans.get('TH', default if default is not None else text)
            return result
        
        # Try to find by matching TH or EN value
        for key, translations in self.translations.items():
            if translations.get('TH') == text:
                # Found by Thai text, return according to current language
                return translations.get(self.current_language, translations.get('TH', text))
            elif translations.get('EN') == text:
                # Found by English text, return according to current language
                return translations.get(self.current_language, translations.get('EN', text))
        
        # If not found and default is provided, check if default exists in translations
        if default:
            if default in self.translations:
                return self.translations[default].get(self.current_language, default)
            # Try to find default by value
            for key, translations in self.translations.items():
                if translations.get('TH') == default or translations.get('EN') == default:
                    return translations.get(self.current_language, default)
        
        # Return original text or default
        return default if default is not None else text
    
    def t(self, text: str, default: Optional[str] = None) -> str:
        """Shortcut for translate()"""
        return self.translate(text, default)
    
    def reload(self):
        """Reload translations from file"""
        self.translations.clear()
        self._load_translations()

# Global translation manager instance
_translation_manager = None

def get_translation_manager() -> TranslationManager:
    """Get global translation manager instance"""
    global _translation_manager
    if _translation_manager is None:
        _translation_manager = TranslationManager()
    return _translation_manager

def t(text: str, default: Optional[str] = None) -> str:
    """Global translation function"""
    return get_translation_manager().translate(text, default)

