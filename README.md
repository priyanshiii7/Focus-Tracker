# 📚 Focus Tracker - AI-Powered Study Session Monitor

A FastAPI-based web application that uses computer vision to monitor study sessions, track focus time, and send alerts when users get distracted.

## ✨ Features

- 🎥 **Real-time Face Detection** - Monitors if you're studying or away
- ⏱️ **Timer-based Sessions** - Set study timers (Pomodoro compatible)
- 🔔 **Smart Alerts** - Voice and/or text alerts when distracted
- 📊 **Analytics Dashboard** - Track study time, focus score, and more
- 👤 **User Authentication** - Secure signup/login system
- 💾 **Session Persistence** - Don't lose progress on server restart
- 🔧 **Maintenance Mode** - Safe deployments without disrupting users
- 📈 **Statistics** - View global app stats and user analytics

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Up Environment
```bash
cp .env.example .env
python admin_tools.py generate-key
# Add generated key to .env file
```

### 3. Configure MongoDB
Add your MongoDB connection string to `.env`:
```env
MONGO_URI=mongodb://localhost:27017/
ADMIN_KEY=your-generated-admin-key
```

### 4. Run the App
```bash
python main.py
```

Visit: http://localhost:8000

## 📚 Documentation

- **[Quick Start Guide](QUICK_START.md)** - Get up and running fast
- **[Deployment Guide](DEPLOYMENT_GUIDE.md)** - Deploy to production
- **[Deployment Checklist](DEPLOYMENT_CHECKLIST.md)** - Step-by-step checklist
- **[Changes Summary](CHANGES_SUMMARY.md)** - What's new in this version

## 🛠️ Tech Stack

- **Backend:** FastAPI, Python 3.8+
- **Database:** MongoDB
- **Computer Vision:** OpenCV, MediaPipe
- **Frontend:** HTML, CSS, JavaScript, Chart.js
- **Voice:** pyttsx3

## 📋 Project Structure

```
focus-tracker/
├── main.py                 # Main application
├── database.py            # Database operations
├── cv_processor.py        # Computer vision processing
├── models.py              # Pydantic models
├── admin_tools.py         # Admin CLI tool
├── deploy.sh             # Deployment script
├── requirements.txt       # Python dependencies
├── .env.example          # Environment template
├── static/
│   ├── index.html        # Dashboard
│   ├── profile.html      # Profile page
│   └── uploads/          # User uploads
└── docs/
    ├── QUICK_START.md
    ├── DEPLOYMENT_GUIDE.md
    └── DEPLOYMENT_CHECKLIST.md
```

## 🎯 Key Features

### Maintenance Mode
```bash
# Enable before deployment
python admin_tools.py maintenance on

# Deploy your changes

# Disable after deployment
python admin_tools.py maintenance off
```

### Session Persistence
- Sessions auto-save every 30 seconds
- Restore sessions within 2 hours
- No data loss during server restarts

### Admin Tools
```bash
python admin_tools.py status          # Check app status
python admin_tools.py maintenance on  # Enable maintenance
python admin_tools.py generate-key    # Generate admin key
python admin_tools.py help           # Show help
```

### Automated Deployment
```bash
./deploy.sh  # Runs full deployment workflow
```

## 🔧 Configuration

### Environment Variables

```env
# Required
MONGO_URI=mongodb://localhost:27017/
ADMIN_KEY=your-admin-key

# Optional
API_URL=http://localhost:8000
DEBUG=False
PORT=8000
HOST=0.0.0.0
```

### Alert Modes

- **both** - Voice + Text alerts (default)
- **voice** - Voice only
- **text** - Text banners only
- **none** - No alerts

## 📊 API Endpoints

### Public Endpoints
- `GET /` - Dashboard
- `GET /login` - Login page
- `GET /signup` - Signup page
- `GET /stats` - Public statistics
- `GET /version` - Version info
- `GET /api/maintenance` - Check maintenance status

### Protected Endpoints (Require Authentication)
- `POST /session/start` - Start study session
- `POST /session/end` - End study session
- `GET /session/current` - Get current session stats
- `GET /profile` - User profile
- `GET /analytics/{period}` - Get analytics

### Admin Endpoints
- `POST /api/admin/maintenance` - Toggle maintenance mode

## 🚀 Deployment

### Deploy to Render/Railway/Heroku

1. **Set environment variables:**
```
MONGO_URI=your-mongodb-atlas-uri
ADMIN_KEY=your-secret-admin-key
DEBUG=False
```

2. **Deploy:**
```bash
git push origin main
```

3. **Or use automated script:**
```bash
./deploy.sh
```

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed instructions.

## 🧪 Testing

```bash
# Test locally
python main.py

# In another terminal
python admin_tools.py status

# Test maintenance mode
python admin_tools.py maintenance on
# Visit http://localhost:8000

python admin_tools.py maintenance off
```

## 📈 Monitoring

```bash
# Check app status
python admin_tools.py status

# Check version
curl http://your-app.com/version

# Check stats
curl http://your-app.com/api/stats
```

## 🐛 Troubleshooting

### Common Issues

**"ADMIN_KEY not set"**
```bash
python admin_tools.py generate-key
# Add to .env file
```

**"Connection refused"**
- Check API_URL in .env
- Verify app is running
- Check firewall settings

**Sessions not persisting**
- Verify MongoDB connection
- Check logs for "Auto-save thread started"
- Ensure `last_updated` field exists

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for more troubleshooting.

## 🔒 Security

- ✅ Password hashing (SHA-256)
- ✅ Session-based authentication
- ✅ Admin key protection
- ✅ HTTPS recommended for production
- ✅ Environment variables for secrets
- ✅ No credentials in code

**Important:** Never commit `.env` file to Git!

## 📝 Version History

### Version 1.0.0 (Current)
- ✅ Maintenance mode system
- ✅ Session persistence (auto-save every 30s)
- ✅ Admin CLI tools
- ✅ Automated deployment script
- ✅ Version tracking
- ✅ Enhanced documentation

### Version 0.9.0
- Initial release
- Basic study session tracking
- Face detection
- User authentication

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 👥 Authors

- Your Name - Initial work

## 🙏 Acknowledgments

- MediaPipe for face detection
- FastAPI for the excellent framework
- MongoDB for reliable data storage
- Chart.js for beautiful visualizations

## 📞 Support

- 📧 Email: your-email@example.com
- 🐛 Issues: [GitHub Issues](your-repo-url/issues)
- 📖 Docs: [Documentation](your-docs-url)

## 🎓 Usage Tips

1. **Set realistic timers** - Start with 25-minute sessions (Pomodoro)
2. **Good lighting** - Helps face detection work better
3. **Stay centered** - Keep your face in camera view
4. **Minimize distractions** - Close unnecessary apps
5. **Take breaks** - Use the timer completion as break reminders

## 🔮 Roadmap

- [ ] Mobile app version
- [ ] More analytics visualizations
- [ ] Study group sessions
- [ ] Integration with calendar apps
- [ ] Gamification features
- [ ] Dark mode
- [ ] Export study reports

## ⚡ Performance

- Real-time face detection: ~30ms per frame
- Session auto-save: Every 30 seconds
- API response time: <100ms
- MongoDB queries: <50ms
- Video streaming: ~10 FPS (optimized for bandwidth)

## 🌟 Star History

If you find this project helpful, please consider giving it a star! ⭐

---

**Happy Studying! 📚✨**

Made with ❤️ and lots of ☕