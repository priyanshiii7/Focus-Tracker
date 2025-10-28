# 📚 Focus Tracker - AI-Powered Study Monitor

An intelligent study session tracker that uses computer vision to detect if you're studying, distracted, or away from your desk. Features voice and text alerts to keep you focused!

## ✨ Features

- **Real-time Focus Detection**: Uses MediaPipe and OpenCV to detect:
  - Studying (focused on work)
  - Distracted (phone usage, poor posture)
  - Away (not at desk)

- **Smart Alerts**:
  - **Voice Alerts**: Assistant speaks reminders
  - **Text Alerts**: Big red warning on screen
  - Customizable alert preferences

- **Comprehensive Analytics**:
  - Daily, weekly, and monthly statistics
  - GitHub-style activity heatmap
  - Focus score tracking
  - Session history

- **MongoDB Integration**: All data persisted for long-term tracking

## 🚀 Setup Instructions

### 1. Install Dependencies

```bash
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install required packages
pip install -r requirements.txt
```

### 2. Install and Start MongoDB

**Option A: MongoDB Community Edition**
- Download from: https://www.mongodb.com/try/download/community
- Install and start MongoDB service
- Default connection: `mongodb://localhost:27017/`

**Option B: MongoDB Atlas (Cloud)**
- Create free account at: https://www.mongodb.com/cloud/atlas
- Create a cluster
- Get connection string
- Add to `.env` file

### 3. Create .env File

Create a `.env` file in project root:

```env
MONGO_URI=mongodb://localhost:27017/
```

### 4. Create static Folder

```bash
mkdir static
```

Move `index.html` to `static/index.html`

### 5. Run the Application

```bash
python main.py
```

The app will start at:
- Dashboard: http://localhost:8000
- API Docs: http://localhost:8000/docs

## 📁 Project Structure

```
Focus-Tracker/
├── main.py              # FastAPI server
├── cv_processor.py      # Computer vision + alerts
├── database.py          # MongoDB operations
├── models.py            # Pydantic models
├── requirements.txt     # Dependencies
├── .env                 # Environment variables
├── .gitignore          # Git ignore file
├── static/
│   └── index.html      # Dashboard UI
└── venv/               # Virtual environment (not in git)
```

## 🎯 Usage

### Starting a Session

1. Open http://localhost:8000
2. Enter your name
3. Select alert preference (Voice/Text/Both)
4. Click "Start Session"
5. Allow webcam access

### During Session

- The system monitors your study behavior
- **Green**: Studying ✅
- **Red**: Distracted (phone, poor posture) ⚠️
- **Orange**: Away from desk 🚶

If distracted for >10 seconds:
- **Voice mode**: Assistant speaks reminder
- **Text mode**: Red alert banner appears
- **Both**: Voice + text alerts

### Viewing Analytics

Click tabs to view:
- **Today**: Current day stats
- **This Week**: 7-day overview with heatmap
- **This Month**: 30-day statistics

## 🔧 Configuration

### Alert Cooldown
Edit in `cv_processor.py`:
```python
self.alert_cooldown = 30  # seconds between alerts
```

### Distraction Threshold
Edit in `cv_processor.py`:
```python
self.distraction_threshold = 10  # seconds before alerting
```

### Custom Alert Messages
Edit in `cv_processor.py`:
```python
self.messages = [
    "Your custom message here!",
    # Add more messages
]
```

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'fastapi'"
```bash
# Make sure venv is activated
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### "Failed to grab frame"
- Check webcam is connected
- Close other apps using webcam
- Try different USB port

### "No active user" error
- Make sure MongoDB is running
- Check connection string in `.env`

### NumPy version conflicts
```bash
pip uninstall numpy
pip install "numpy<2.0"
```

### Voice alerts not working
```bash
# Windows: Install additional dependencies
pip install pywin32
```

## 📊 MongoDB Collections

### users
- User profiles and preferences
- Total study hours

### sessions
- Individual study sessions
- Focus intervals
- Alerts triggered

### daily_stats
- Aggregated daily statistics

## 🔐 Privacy

- All video processing happens locally
- No video is recorded or stored
- Only session metrics saved to database
- Webcam feed never leaves your device

## 🤝 Contributing

Feel free to submit issues and enhancement requests!

## 📝 License

MIT License - feel free to use for personal or educational purposes

## 🎓 Tips for Best Results

1. **Good Lighting**: Helps face detection
2. **Stable Position**: Don't move camera during session
3. **Clear View**: Ensure face is visible to webcam
4. **Consistent Setup**: Same desk position helps accuracy

## 📈 Future Enhancements

- [ ] Break reminders (Pomodoro technique)
- [ ] Mobile app
- [ ] Multi-user support
- [ ] Export data to CSV
- [ ] Integration with calendar
- [ ] Productivity insights with AI

---

Made with ❤️ for focused studying!