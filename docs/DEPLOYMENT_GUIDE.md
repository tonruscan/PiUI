# Deployment Guide - Refactored UI

## 🎯 Important: Development vs. Target Device

This code is being developed on a **Windows network drive** but will run on a **different target device** (likely Raspberry Pi/Linux with physical display).

---

## 🖥️ Target Device Requirements

### **Hardware**
- Raspberry Pi (or similar) with display
- MIDI interface (if applicable)
- Network connection
- Physical display (800x480 touchscreen)

### **Software/Packages**
```bash
# Python 3.7+
python3 --version

# Required packages (on target device)
pip3 install pygame
pip3 install python-rtmidi  # for MIDI
# Add any other dependencies from your original setup
```

---

## 📦 Deployment Steps

### **Step 1: Sync Code to Target Device**

From your development machine (Windows):
```powershell
# Option A: If using git
cd t:\UI\build
git add .
git commit -m "Refactored UI to modular architecture"
git push

# On target device:
git pull

# Option B: Direct copy via network/rsync
# (adjust paths as needed)
```

### **Step 2: Verify File Structure on Target**

On the target device:
```bash
cd /path/to/UI/build
ls -la

# Should see:
# - ui.py (original - keep as backup)
# - ui_new.py (new entry point)
# - core/
# - managers/
# - rendering/
# - initialization/
# - handlers/
# - pages/ (existing)
# - control/ (existing)
# - system/ (existing)
# etc.
```

### **Step 3: Check Python Environment**

On target device:
```bash
# Verify Python
python3 --version

# Verify pygame
python3 -c "import pygame; print(pygame.version.ver)"

# Verify other dependencies
python3 -c "import midiserver, network, cv_client, dialhandlers"
```

### **Step 4: Test Import Structure**

On target device:
```bash
cd /path/to/UI/build
python3 test_refactored.py
```

**Expected output:**
```
============================================================
UI Refactoring Test Suite
============================================================
✓ Core modules imported
✓ Manager modules imported
✓ Rendering modules imported
✓ Initialization modules imported
✓ Handler modules imported
✓ DialManager created
✓ ButtonManager created
✓ ModeManager created
✓ Button selection works
✓ Button memory works
✓ Dial creation works

✓ All tests passed! Ready to run ui_new.py
```

---

## 🚀 Running the New Architecture

### **Option 1: Test New Architecture (Safe)**

```bash
# Run the new modular version
python3 ui_new.py
```

If it crashes or has issues:
- Check the error messages
- The original `ui.py` is still intact
- You can always fall back

### **Option 2: Run Original (Fallback)**

```bash
# Run the original version (always works)
python3 ui.py
```

---

## 🐛 Common Issues & Solutions

### **Issue 1: Import Errors**
```
ModuleNotFoundError: No module named 'core'
```

**Solution:**
```bash
# Make sure you're in the correct directory
cd /path/to/UI/build
pwd  # Should show .../UI/build

# Python path might need adjustment
export PYTHONPATH=/path/to/UI/build:$PYTHONPATH
```

### **Issue 2: Display Not Found**
```
pygame.error: No available video device
```

**Solution:**
```bash
# Make sure you're running on the device with display
# Check DISPLAY variable
echo $DISPLAY

# If running via SSH, you might need:
export DISPLAY=:0
```

### **Issue 3: Permission Errors (MIDI/Hardware)**
```
PermissionError: [Errno 13] Permission denied: '/dev/midi'
```

**Solution:**
```bash
# Add user to appropriate groups
sudo usermod -a -G audio $USER
sudo usermod -a -G input $USER

# Log out and back in
```

### **Issue 4: Config Not Found**
```
AttributeError: module 'config' has no attribute 'SCREEN_WIDTH'
```

**Solution:**
```bash
# Make sure config.py exists in the same directory
ls -la config.py

# Check config.py has the required settings
cat config.py | grep SCREEN_WIDTH
```

---

## 🔄 Safe Migration Strategy

### **Phase 1: Parallel Testing (Recommended)**

1. **Keep both versions running:**
   - `ui.py` - Original (known working)
   - `ui_new.py` - New modular version

2. **Test new version:**
   ```bash
   # Test for 5 minutes
   python3 ui_new.py
   
   # Press Escape to exit
   # Check for any errors/crashes
   ```

3. **Compare behavior:**
   - Does device selection work?
   - Do dials respond?
   - Does page navigation work?
   - Are presets loading correctly?

### **Phase 2: Feature Verification**

Test each feature systematically:

```bash
# Start new UI
python3 ui_new.py

# Test checklist:
# [ ] Device selection screen appears
# [ ] Can select a device
# [ ] Dials page loads
# [ ] Dials respond to mouse/touch
# [ ] Button clicks work
# [ ] Page navigation works (back button)
# [ ] Presets page works
# [ ] MIDI input works
# [ ] Hardware dials work
# [ ] State persists between pages
```

### **Phase 3: Replace Original (When Ready)**

Only after confirming everything works:

```bash
# Backup original
cp ui.py ui_original_backup.py

# Replace with new version
mv ui_new.py ui.py

# Update any startup scripts
# (if ui.py is called from systemd, cron, etc.)
```

---

## 📊 Performance Comparison

On target device, compare performance:

```bash
# Original version
python3 ui_original_backup.py
# Note: FPS, responsiveness, memory usage

# New version
python3 ui.py
# Compare: Should be similar or better
```

---

## 🔧 Development Workflow

Since development is on Windows but execution is on target device:

1. **Edit code on Windows** (t:\UI\build)
2. **Sync to target device** (git/rsync/network copy)
3. **Test on target device** (SSH or direct)
4. **Iterate** (repeat 1-3)

**Tip:** Use SSH with X11 forwarding to see output:
```bash
# From Windows (if you have X server)
ssh -X user@targetdevice
cd /path/to/UI/build
python3 ui_new.py
```

---

## 📝 Logging & Debugging

The new architecture uses the same logging as before:

```python
# Check logs on target device
tail -f ui_log.txt

# Or in code, increase logging:
# In config.py, set:
DEBUG = True
VERBOSE = True
```

---

## ✅ Pre-Deployment Checklist

Before deploying to target device:

- [ ] All new folders created (core/, managers/, etc.)
- [ ] All new files present
- [ ] Original ui.py kept as backup
- [ ] test_refactored.py included
- [ ] Documentation files included (REFACTORING_GUIDE.md, etc.)
- [ ] No Windows-specific paths in code
- [ ] No pygame.display calls without try/except
- [ ] All imports use relative paths

---

## 🆘 Rollback Procedure

If the new version doesn't work:

```bash
# Stop the new version
# Press Escape or Ctrl+C

# Run original
python3 ui_original_backup.py

# Or if you already replaced ui.py:
git checkout ui.py  # if using git
# or
cp ui_original_backup.py ui.py
```

---

## 📞 Next Steps

1. **On target device:** Run `python3 test_refactored.py`
2. **If tests pass:** Run `python3 ui_new.py`
3. **Test all features** systematically
4. **Report any issues** for debugging
5. **When stable:** Replace original

---

## 💡 Pro Tips

- **Test incrementally** - Don't try everything at once
- **Keep logs** - `showlog` will help debug issues
- **Use SSH** - Easier to see errors in terminal
- **Keep backup** - Always have ui.py working
- **Git commits** - Commit each working state

---

**Remember:** The network drive is just for development. All actual testing must happen on the target device with the real hardware!
