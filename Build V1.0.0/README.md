# FREE Football Analysis - Build Guide

## วิธี Build

### วิธีที่ 1: PyInstaller (แนะนำ - เร็วกว่า)

```batch
cd "Build V1.0.0"
build_exe.bat
```

**ข้อดี:**
- ✅ Build เร็ว (5-15 นาที)
- ✅ แก้ปัญหา QtMultimedia แล้ว
- ✅ ใช้งานง่าย

**ผลลัพธ์:** `dist\FREE_Football_Analysis\FREE_Football_Analysis.exe`

---

### วิธีที่ 2: Nuitka (ช้ากว่า แต่ performance ดีกว่า)

```batch
cd "Build V1.0.0"
BUILD_WITH_NUITKA.bat
```

**ข้อดี:**
- ✅ Performance ดีกว่า (native code)
- ✅ Bundle size เล็กกว่า

**ข้อเสีย:**
- ❌ Build ช้ามาก (30-60+ นาที)

**ผลลัพธ์:** `dist\run_desktop_app.dist\FREE_Football_Analysis.exe`

---

## ไฟล์ที่จำเป็น

### สำหรับ PyInstaller:
- `FREE_Football_Analysis.spec` - Configuration file
- `build_exe.bat` - Build script
- `pyi_rth_python_dll.py` - Runtime hook
- `pyi_rth_torch.py` - Runtime hook

### สำหรับ Nuitka:
- `BUILD_WITH_NUITKA.bat` - Build script
- `get_cores.py` - Helper script

---

## หมายเหตุ

- ต้องมี Python และ dependencies ติดตั้งอยู่แล้ว
- ไฟล์ .exe อาจมีขนาดใหญ่ (500MB - 1GB)
- ควรทดสอบ .exe ก่อนแจกจ่าย
- ดู `BUILD_COMPARISON.md` สำหรับรายละเอียดเพิ่มเติม

