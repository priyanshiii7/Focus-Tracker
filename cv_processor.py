import cv2
import mediapipe as mp
import time
from datetime import datetime
import pyttsx3
import threading
import numpy as np

class FocusDetector:
    def __init__(self):
        self.mp_face_detection = mp.solutions.face_detection
        self.face_detection = self.mp_face_detection.FaceDetection(
            min_detection_confidence=0.4,  # Lower threshold for better detection
            model_selection=0
        )
        
        # Improved counters with better thresholds
        self.frames_with_face = 0
        self.frames_without_face = 0
        
        # OPTIMIZED THRESHOLDS
        self.away_threshold = 8        # 8 frames without face = away (≈4 seconds)
        self.return_threshold = 3      # 3 frames with face = back (≈1.5 seconds)
        
        print("✅ FocusDetector initialized with optimized thresholds")
        
    def detect_status(self, frame):
        """Analyze frame and return current status with improved accuracy"""
        if frame is None:
            return "away"
        
        try:
            # Convert to RGB for MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_results = self.face_detection.process(rgb_frame)
            
            has_face = face_results.detections is not None and len(face_results.detections) > 0
            
            if has_face:
                # Face detected
                self.frames_with_face += 1
                self.frames_without_face = 0
                
                # Need consecutive frames to confirm "studying"
                if self.frames_with_face >= self.return_threshold:
                    return "studying"
                else:
                    # Not enough consecutive frames yet, maintain previous state
                    return "transitioning_to_studying"
            else:
                # No face detected
                self.frames_without_face += 1
                self.frames_with_face = 0
                
                # Need consecutive frames to confirm "away"
                if self.frames_without_face >= self.away_threshold:
                    return "away"
                else:
                    # Not enough consecutive frames yet, maintain previous state
                    return "transitioning_to_away"
                    
        except Exception as e:
            print(f"⚠️  Detection error: {e}")
            return "away"
    
    def reset_counters(self):
        """Reset frame counters"""
        self.frames_with_face = 0
        self.frames_without_face = 0
    
    def cleanup(self):
        """Clean up MediaPipe resources"""
        try:
            if self.face_detection is not None and hasattr(self.face_detection, 'close'):
                self.face_detection.close()
                self.face_detection = None
        except Exception as e:
            print(f"⚠️  Error cleaning up face detection: {e}")


class AlertSystem:
    def __init__(self, mode="both"):
        self.mode = mode
        self.engine = None
        self.last_alert_time = 0
        self.alert_cooldown = 60  # 60 seconds between alerts
        self.is_speaking = False
        
        if mode in ["voice", "both"]:
            try:
                self.engine = pyttsx3.init()
                self.engine.setProperty('rate', 160)
                self.engine.setProperty('volume', 1.0)
                print("✅ Voice engine initialized")
            except Exception as e:
                print(f"⚠️  Voice engine failed: {e}")
                self.engine = None
        
        self.warning_messages = [
            "Hey! Stop looking away and get back to studying!",
            "Focus! Your study session is running!",
            "I see you're not studying. Time to refocus!",
            "Get back to work right now!",
            "Stop wasting time! Focus on your studies!",
            "You need to concentrate! Back to your books!",
            "Come on! Your timer is still running. Get back to work!"
        ]
        
        self.current_message_index = 0
    
    def trigger_alert(self, status, alert_type="warning"):
        """Trigger alert based on status"""
        current_time = time.time()
        
        # Check cooldown
        if current_time - self.last_alert_time < self.alert_cooldown:
            return None
        
        self.last_alert_time = current_time
        message = self.warning_messages[self.current_message_index]
        self.current_message_index = (self.current_message_index + 1) % len(self.warning_messages)
        
        alert_data = {
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "type": self.mode,
            "alert_level": alert_type
        }
        
        print(f"🔔 ALERT TRIGGERED: {message}")
        
        # Voice alert (non-blocking)
        if self.mode in ["voice", "both"] and self.engine and not self.is_speaking:
            threading.Thread(target=self._speak, args=(message,), daemon=True).start()
        
        return alert_data
    
    def _speak(self, message):
        """Speak the message"""
        try:
            self.is_speaking = True
            self.engine.say(message)
            self.engine.runAndWait()
            self.is_speaking = False
        except Exception as e:
            print(f"⚠️  Voice alert failed: {e}")
            self.is_speaking = False


class CVProcessor:
    def __init__(self, callback=None, alert_mode="both"):
        self.detector = FocusDetector()
        self.alert_system = AlertSystem(mode=alert_mode)
        
        # Try to open camera
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(1)
        
        if not self.cap.isOpened():
            raise Exception("Could not open camera")
        
        # OPTIMIZED camera settings for better performance
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
        self.cap.set(cv2.CAP_PROP_FPS, 20)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        self.is_running = False
        self.callback = callback
        self.current_status = "studying"
        self.last_confirmed_status = "studying"
        
        # Timing
        self.away_start_time = None
        self.away_warnings = 0
        self.last_alert_time = 0
        self.alert_interval = 60  # Alert every 60 seconds
        
        # Video streaming
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        
        # Performance tracking
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.fps = 0
        
        print("✅ CV Processor initialized with optimized settings")
        
    def start(self):
        """Start the CV processing loop with improved logic"""
        self.is_running = True
        print("🎥 CV Processor started - monitoring with improved detection...")
        
        self.detector.reset_counters()
        
        while self.is_running:
            ret, frame = self.cap.read()
            
            if not ret or frame is None:
                time.sleep(0.05)
                continue
            
            # Store frame for streaming
            with self.frame_lock:
                self.latest_frame = frame.copy()
            
            # Detect status
            status = self.detector.detect_status(frame)
            current_time = time.time()
            
            # Calculate FPS for debugging
            self.frame_count += 1
            if current_time - self.last_fps_time >= 1.0:
                self.fps = self.frame_count / (current_time - self.last_fps_time)
                self.frame_count = 0
                self.last_fps_time = current_time
            
            # Handle transitioning states
            if status == "transitioning_to_studying" or status == "transitioning_to_away":
                # Don't change status yet, wait for confirmation
                time.sleep(0.05)
                continue
            
            # Only process confirmed states
            if status != self.last_confirmed_status:
                print(f"🔄 Status CONFIRMED: {self.last_confirmed_status} → {status} (FPS: {self.fps:.1f})")
                
                # Update confirmed status
                self.last_confirmed_status = status
                
                # Trigger callback for status change
                if self.callback:
                    self.callback(status, None)
                
                # Reset away tracking when returning
                if status == "studying":
                    if self.away_start_time is not None:
                        print(f"✅ User returned - warnings reset")
                    self.away_start_time = None
                    self.away_warnings = 0
                
                # Start tracking away time
                elif status == "away":
                    self.away_start_time = current_time
                    print(f"⏱️  User went away at {datetime.now().strftime('%H:%M:%S')}")
            
            # Handle prolonged absence
            if self.last_confirmed_status == "away" and self.away_start_time:
                time_away = current_time - self.away_start_time
                
                # Alert after alert_interval seconds
                if time_away >= self.alert_interval and (current_time - self.last_alert_time) >= self.alert_interval:
                    self.away_warnings += 1
                    
                    print(f"\n{'='*60}")
                    print(f"🚨 WARNING #{self.away_warnings}")
                    print(f"   Time away: {time_away:.0f}s")
                    
                    alert = self.alert_system.trigger_alert(status, "warning")
                    
                    if alert and self.callback:
                        print(f"   ✅ Alert sent to callback")
                        self.callback(status, alert)
                    
                    print(f"{'='*60}\n")
                    
                    self.last_alert_time = current_time
                    
                    # End session after 3 warnings
                    if self.away_warnings >= 3:
                        print("❌ 3 warnings reached! Ending session...")
                        if self.callback:
                            self.callback("session_end", {
                                "reason": "Too much time away from studies",
                                "timestamp": datetime.now().isoformat()
                            })
                        self.stop()
                        return
            
            # Process at 20 FPS for smooth detection
            time.sleep(0.05)
        
        print("🛑 CV Processing loop ended")
    
    def get_frame(self):
        """Get latest frame for streaming"""
        with self.frame_lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
            return None
    
    def stop(self):
        """Stop the CV processing"""
        print("🛑 Stopping CV processor...")
        self.is_running = False
        time.sleep(0.2)
        if self.cap:
            self.cap.release()
        self.detector.cleanup()
        print("✅ CV processor stopped")
    
    def get_current_status(self):
        """Get current focus status"""
        return self.last_confirmed_status
    
    def set_alert_mode(self, mode):
        """Change alert mode"""
        self.alert_system = AlertSystem(mode=mode)
        print(f"🔔 Alert mode changed to: {mode}")