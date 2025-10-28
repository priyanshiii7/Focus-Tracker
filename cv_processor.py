import cv2
import mediapipe as mp
import time
from datetime import datetime

class FocusDetector:
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.mp_hands = mp.solutions.hands
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.hands = self.mp_hands.Hands(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        self.current_status = "focused"
        self.last_status_change = time.time()
        
    def detect_status(self, frame):
        """
        Analyze frame and return current status
        Returns: "focused", "away", or "phone_detected"
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Pose detection
        pose_results = self.pose.process(rgb_frame)
        hands_results = self.hands.process(rgb_frame)
        
        # Check if person is away (no pose detected)
        if not pose_results.pose_landmarks:
            return "away"
        
        # Check for phone usage (hand near face)
        if hands_results.multi_hand_landmarks and pose_results.pose_landmarks:
            if self._is_phone_detected(hands_results, pose_results):
                return "phone_detected"
        
        # Check if looking at screen (head pose analysis)
        if self._is_looking_away(pose_results):
            return "away"
        
        return "focused"
    
    def _is_phone_detected(self, hands_results, pose_results):
        """Detect if hand is near face (phone usage)"""
        try:
            nose = pose_results.pose_landmarks.landmark[self.mp_pose.PoseLandmark.NOSE]
            
            for hand_landmarks in hands_results.multi_hand_landmarks:
                wrist = hand_landmarks.landmark[self.mp_hands.HandLandmark.WRIST]
                
                # Calculate distance between hand and face
                distance = ((nose.x - wrist.x)**2 + (nose.y - wrist.y)**2)**0.5
                
                # If hand is close to face
                if distance < 0.2:
                    return True
            
            return False
        except:
            return False
    
    def _is_looking_away(self, pose_results):
        """Detect if user is looking away from screen"""
        try:
            nose = pose_results.pose_landmarks.landmark[self.mp_pose.PoseLandmark.NOSE]
            left_ear = pose_results.pose_landmarks.landmark[self.mp_pose.PoseLandmark.LEFT_EAR]
            right_ear = pose_results.pose_landmarks.landmark[self.mp_pose.PoseLandmark.RIGHT_EAR]
            
            # Check head rotation based on ear positions
            ear_diff = abs(left_ear.x - right_ear.x)
            
            # If ears are too close (head turned sideways)
            if ear_diff < 0.05:
                return True
            
            # Check if nose is too far left or right
            if nose.x < 0.3 or nose.x > 0.7:
                return True
            
            return False
        except:
            return False
    
    def cleanup(self):
        """Release resources"""
        self.pose.close()
        self.hands.close()


class CVProcessor:
    def __init__(self, callback=None):
        self.detector = FocusDetector()
        self.cap = cv2.VideoCapture(0)
        self.is_running = False
        self.callback = callback  # Function to call on status change
        self.current_status = "focused"
        
    def start(self):
        """Start the CV processing loop"""
        self.is_running = True
        
        while self.is_running:
            ret, frame = self.cap.read()
            
            if not ret:
                print("Failed to grab frame")
                break
            
            # Detect status every frame
            status = self.detector.detect_status(frame)
            
            # If status changed, trigger callback
            if status != self.current_status:
                print(f"Status changed: {self.current_status} -> {status}")
                self.current_status = status
                
                if self.callback:
                    self.callback(status)
            
            # Optional: Display the frame (for debugging)
            # cv2.imshow('Focus Tracker', frame)
            
            # Break on 'q' key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            # Check every 100ms (10 fps is enough)
            time.sleep(0.1)
    
    def stop(self):
        """Stop the CV processing"""
        self.is_running = False
        self.cap.release()
        self.detector.cleanup()
        cv2.destroyAllWindows()
    
    def get_current_status(self):
        """Get current focus status"""
        return self.current_status