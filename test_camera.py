import cv2
import mediapipe as mp
import time

print("🎥 Testing camera and face detection...")

# Try to open camera
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("❌ Camera 0 failed, trying camera 1...")
    cap = cv2.VideoCapture(1)

if not cap.isOpened():
    print("❌ No camera found!")
    exit(1)

print("✅ Camera opened successfully")

# Set properties
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

# Initialize MediaPipe
mp_face = mp.solutions.face_detection
face_detection = mp_face.FaceDetection(min_detection_confidence=0.3)
mp_draw = mp.solutions.drawing_utils

print("✅ MediaPipe initialized")
print("\n📹 Press 'q' to quit\n")

frame_count = 0
face_detected_count = 0

while True:
    ret, frame = cap.read()
    frame_count += 1
    
    if not ret:
        print("❌ Failed to grab frame")
        break
    
    # Convert to RGB
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Detect faces
    results = face_detection.process(rgb_frame)
    
    # Draw results
    if results.detections:
        face_detected_count += 1
        for detection in results.detections:
            mp_draw.draw_detection(frame, detection)
            
            # Draw status text
            cv2.putText(frame, "FACE DETECTED - Studying", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    else:
        cv2.putText(frame, "NO FACE - Away", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    
    # Show stats
    detection_rate = (face_detected_count / frame_count * 100) if frame_count > 0 else 0
    cv2.putText(frame, f"Frames: {frame_count} | Faces: {face_detected_count} ({detection_rate:.1f}%)", 
               (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    # Display
    cv2.imshow('Focus Tracker - Camera Test', frame)
    
    # Quit on 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    
    # Print status every 30 frames
    if frame_count % 30 == 0:
        status = "✅ DETECTED" if results.detections else "❌ NOT DETECTED"
        print(f"Frame {frame_count}: Face {status}")

cap.release()
cv2.destroyAllWindows()
face_detection.close()

print(f"\n📊 Test Results:")
print(f"   Total Frames: {frame_count}")
print(f"   Faces Detected: {face_detected_count}")
print(f"   Detection Rate: {detection_rate:.1f}%")

if detection_rate > 50:
    print("✅ Camera and detection working well!")
else:
    print("⚠ Low detection rate - check lighting and camera position")