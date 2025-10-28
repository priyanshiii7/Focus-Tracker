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
            min_detection_confidence=0.3,  # Lower threshold for better detection
            model_selection=0
        )
        
        self.frames_without_face = 0
        self.away_threshold = 10  # ~5 seconds at 0.5s intervals
        
    def detect_status(self, frame):
        """
        Analyze frame and return current status
        Returns: "studying" or "away"
        """
        if frame is None:
            return "away"
            
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Run face detection only (removed phone detection)
        face_results = self.face_detection.process(rgb_frame)
        
        # Check if face is detected
        if not face_results.detections:
            self.frames_without_face += 1
            
            # Only mark as away after threshold
            if self.frames_without_face >= self.away_threshold:
                if self.frames_without_face % 20 == 0:  # Log every 10 seconds
                    print(f"⚠ No face - frame count: {self.frames_without_face}")
                return "away"
            else:
                return "studying"  # Grace period
        else:
            # Face detected - reset counter
            was_away = self.frames_without_face >= self.away_threshold
            self.frames_without_face = 0
            
            if was_away:
                print("✅ Face detected - back to studying")
            
            # Always studying when face is visible
            return "studying"
    
    def _is_phone_detected(self, hands_results, face_results):
        """Detect if hand is near face (phone usage)"""
        try:
            face_box = face_results.detections[0].location_data.relative_bounding_box
            face_center_x = face_box.xmin + face_box.width / 2
            face_center_y = face_box.ymin + face_box.height / 2
            
            for hand_landmarks in hands_results.multi_hand_landmarks:
                wrist = hand_landmarks.landmark[self.mp_hands.HandLandmark.WRIST]
                
                # Calculate distance
                distance = ((face_center_x - wrist.x)**2 + (face_center_y - wrist.y)**2)**0.5
                
                if distance < 0.25:
                    return True
            
            return False
        except:
            return False
    
    def cleanup(self):
        """Release resources"""
        self.face_detection.close()
        self.hands.close()


class AlertSystem:
    def __init__(self, mode="both"):
        self.mode = mode
        self.engine = None
        self.last_alert_time = 0
        self.alert_cooldown = 60  # 1 MINUTE between alerts
        self.is_speaking = False
        
        if mode in ["voice", "both"]:
            try:
                self.engine = pyttsx3.init()
                self.engine.setProperty('rate', 160)
                self.engine.setProperty('volume', 1.0)
                print("✓ Voice engine initialized")
            except Exception as e:
                print(f"⚠ Voice engine failed: {e}")
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
        
        print(f"🔔 ALERT: {message}")
        
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
            print("✓ Voice alert completed")
        except Exception as e:
            print(f"⚠ Voice alert failed: {e}")
            self.is_speaking = False


class CVProcessor:
    def __init__(self, callback=None, alert_mode="both"):
        self.detector = FocusDetector()
        self.alert_system = AlertSystem(mode=alert_mode)
        
        # Try to open camera
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("⚠ Camera failed to open, trying alternate...")
            self.cap = cv2.VideoCapture(1)
        
        # Set camera properties for better performance
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        self.is_running = False
        self.callback = callback
        self.current_status = "studying"
        
        # Timing
        self.away_start_time = None
        self.distraction_start_time = None
        self.last_alert_time = 0
        self.away_warnings = 0
        self.alert_interval = 60  # Alert every 60 seconds (1 MINUTE)
        
        # Video streaming
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        
        print("✓ CV Processor initialized")
        
    def start(self):
        """Start the CV processing loop"""
        self.is_running = True
        print("🎥 CV Processor started - monitoring...")
        
        frame_count = 0
        
        while self.is_running:
            ret, frame = self.cap.read()
            frame_count += 1
            
            if not ret or frame is None:
                print(f"⚠ Frame grab failed (frame {frame_count})")
                time.sleep(0.1)
                continue
            
            # Store frame for streaming
            with self.frame_lock:
                self.latest_frame = frame.copy()
            
            # Detect status every frame
            status = self.detector.detect_status(frame)
            current_time = time.time()
            
            # Status change callback
            if status != self.current_status:
                print(f"🔄 Status: {self.current_status} → {status}")
                self.current_status = status
                
                if self.callback:
                    self.callback(status, None)
            
            # Handle away status for alerts
            if status == "away":
                if self.away_start_time is None:
                    self.away_start_time = current_time
                
                time_away = current_time - self.away_start_time
                
                # Alert every 60 seconds (1 minute)
                if time_away >= 60 and (current_time - self.last_alert_time) >= self.alert_interval:
                    self.away_warnings += 1
                    alert = self.alert_system.trigger_alert(status, "warning")
                    self.last_alert_time = current_time
                    
                    print(f"🚨 WARNING #{self.away_warnings}: {time_away:.0f}s away - ALERT TRIGGERED!")
                    
                    if alert and self.callback:
                        self.callback(status, alert)
                    
                    # End session after 3 warnings (3 minutes)
                    if self.away_warnings >= 3:
                        print("❌ 3 warnings reached! Ending session...")
                        if self.callback:
                            self.callback("session_end", {
                                "reason": "Too much time away from studies",
                                "timestamp": datetime.now().isoformat()
                            })
                        self.stop()
                        return
            else:
                # Reset away tracking
                if self.away_start_time is not None:
                    self.away_start_time = None
                    self.away_warnings = 0
                    print("✅ Back to studying - warnings reset")
            
            # Sleep for 500ms
            time.sleep(0.5)
    
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
        if self.cap:
            self.cap.release()
        self.detector.cleanup()
    
    def get_current_status(self):
        """Get current focus status"""
        return self.current_status
    
    def set_alert_mode(self, mode):
        """Change alert mode"""
        self.alert_system = AlertSystem(mode=mode)
        print(f"🔔 Alert mode: {mode}")