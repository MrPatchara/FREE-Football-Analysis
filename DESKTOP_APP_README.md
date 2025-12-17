# FREE Football Analysis Desktop Application

## คำอธิบายโปรเจค (Project Description)

**FREE Football Analysis** เป็นระบบวิเคราะห์วิดีโอฟุตบอลอัตโนมัติโดยใช้ Computer Vision และ Deep Learning

### ฟีเจอร์หลัก:

1. **Object Detection & Tracking** - ตรวจจับและติดตามวัตถุในวิดีโอ:
   - ลูกบอล (Ball)
   - ผู้รักษาประตู (Goalkeepers)
   - ผู้เล่น (Players)
   - กรรมการ (Referees)

2. **Team Assignment** - แยกผู้เล่นออกเป็นทีมโดยใช้ KMeans Clustering ตามสีเสื้อ

3. **Ball Possession Tracking** - ติดตามการครอบครองบอลของผู้เล่น

4. **Camera Movement Estimation** - ประมาณการเคลื่อนไหวของกล้องด้วย Optical Flow เพื่อปรับตำแหน่งวัตถุให้แม่นยำ

5. **Ball Position Interpolation** - ปรับปรุงการติดตามบอลด้วยการ Interpolate ตำแหน่งที่ขาดหาย

6. **Statistics Display** - แสดงสถิติการครอบครองบอลในวิดีโอ

### เทคโนโลยีที่ใช้:

- **YOLOv5** (Custom trained model) - สำหรับ Object Detection
- **ByteTrack** - สำหรับ Object Tracking
- **OpenCV** - สำหรับการประมวลผลวิดีโอและภาพ
- **Ultralytics** - สำหรับ YOLO model
- **PyQt6** - สำหรับ Desktop GUI

---

## วิธีใช้งาน Desktop Application

### การติดตั้ง (Installation)

1. ติดตั้ง dependencies:
```bash
pip install -r requirements.txt
```

2. รันแอปพลิเคชัน:
```bash
python run_desktop_app.py
```

หรือ

```bash
python frontend/desktop_app.py
```

### วิธีใช้งาน:

1. **เลือกตัวเลือกการแสดงผล:**
   - ✓ Highlight Players
   - ✓ Highlight Goalkeepers
   - ✓ Highlight Referees
   - ✓ Highlight Ball
   - ✓ Show Statistics

2. **เลือกแหล่งวิดีโอ:**
   - **Demo Videos**: เลือกวิดีโอตัวอย่าง (Demo 1 หรือ Demo 2)
   - **Upload Video**: คลิกปุ่ม "เลือกไฟล์วิดีโอ (MP4)" เพื่ออัปโหลดวิดีโอของคุณ

3. **เริ่มวิเคราะห์:**
   - คลิกปุ่ม "เริ่มวิเคราะห์ (Start Analysis)"
   - รอให้การประมวลผลเสร็จสิ้น (จะแสดง progress bar และ status)

4. **ดูผลลัพธ์:**
   - ไปที่แท็บ "Results" เพื่อดูวิดีโอผลลัพธ์
   - คลิก "เปิดไฟล์ผลลัพธ์" เพื่อเปิดวิดีโอด้วยโปรแกรมเล่นวิดีโอ
   - หรือคลิก "เปิดโฟลเดอร์ผลลัพธ์" เพื่อเปิดโฟลเดอร์ output

5. **ดู Logs:**
   - ไปที่แท็บ "Logs" เพื่อดู log files
   - เลือก log file ที่ต้องการ (Tracking, Camera Movement, หรือ Memory Access)
   - คลิก "รีเฟรช" เพื่อโหลดข้อมูลใหม่

---

## ข้อดีของ Desktop Application

### Desktop Application (PyQt6):
- ✅ ไม่ต้องเปิดเว็บเบราเซอร์
- ✅ ทำงานเป็น standalone desktop application
- ✅ UI ที่เป็นทางการและทันสมัย
- ✅ Performance ที่ดีกว่า
- ✅ รองรับการเปิดไฟล์ผลลัพธ์ด้วยโปรแกรมภายนอก
- ✅ มีปุ่มเปิดโฟลเดอร์ผลลัพธ์
- ✅ Real-time progress tracking
- ✅ Built-in video player สำหรับดูผลลัพธ์

---

## ไฟล์ที่เกี่ยวข้อง:

- `frontend/desktop_app.py` - Desktop GUI application (PyQt6)
- `main.py` - Core video processing logic
- `run_desktop_app.py` - Launcher script

---

## หมายเหตุ:

- วิดีโอที่อัปโหลดต้องเป็นไฟล์ `.mp4`
- สำหรับผลลัพธ์ที่ดีที่สุด วิดีโอควรไม่มีการเปลี่ยนมุมกล้องหลายครั้ง
- ไฟล์ผลลัพธ์จะถูกบันทึกที่ `output/output.mp4`
- Log files จะถูกบันทึกในโฟลเดอร์ `logs/`

