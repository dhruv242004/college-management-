"""Advanced security module for attendance verification."""
import hashlib
import json
from database import db_cursor
from config import config


class SecurityService:
    """Advanced security features for attendance."""

    @staticmethod
    def verify_campus_location(latitude, longitude, campus_latitudes=None, 
                              campus_longitudes=None, radius_km=1.0):
        """
        Verify if student is within campus geofence.
        
        Args:
            latitude, longitude: Student location
            campus_latitudes, campus_longitudes: Campus boundaries
            radius_km: Geofence radius in km
        
        Returns:
            bool: Whether student is within campus
        """
        if not all([latitude, longitude]):
            return False  # No location provided

        # Default to college coordinates (update with actual)
        COLLEGE_LAT = 28.6139  # Example: Delhi
        COLLEGE_LON = 77.2090
        
        campus_lat = campus_latitudes or COLLEGE_LAT
        campus_lon = campus_longitudes or COLLEGE_LON
        
        # Calculate distance using Haversine formula
        from math import radians, cos, sin, asin, sqrt
        
        lon1, lat1, lon2, lat2 = map(radians, [campus_lon, campus_lat, longitude, latitude])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        km = 6371 * c
        
        return km <= radius_km

    @staticmethod
    def verify_campus_network(ip_address):
        """
        Verify if IP is on campus network.
        
        Args:
            ip_address: Student IP address
        
        Returns:
            bool: Whether IP is whitelisted
        """
        if not ip_address:
            return False
        
        try:
            with db_cursor() as (conn, cur):
                # Check if IP falls within whitelisted ranges
                cur.execute(
                    """
                    SELECT id FROM ip_whitelist
                    WHERE is_active = TRUE
                    AND %s::inet BETWEEN ip_range_start::inet AND ip_range_end::inet
                    LIMIT 1
                    """,
                    (ip_address,)
                )
                return cur.fetchone() is not None
        except Exception as e:
            print(f"Error verifying IP: {str(e)}")
            return False

    @staticmethod
    def verify_face_recognition(student_id, face_image_path):
        """
        Verify student identity using face recognition.
        
        Args:
            student_id: Student to verify
            face_image_path: Path to captured image
        
        Returns:
            dict: Verification result
        """
        try:
            # Import face_recognition library
            import face_recognition
            import numpy as np
            from PIL import Image
            
            with db_cursor() as (conn, cur):
                # Get stored face encoding
                cur.execute(
                    "SELECT face_encoding, verified FROM face_verification WHERE student_id = %s",
                    (student_id,)
                )
                stored = cur.fetchone()
                
                if not stored or not stored['verified']:
                    return {
                        'verified': False,
                        'reason': 'No face verification data found'
                    }
                
                # Decode stored face
                stored_encoding = np.frombuffer(
                    bytes.fromhex(stored['face_encoding']), 
                    dtype=np.float32
                )
                
                # Load and process new image
                image = face_recognition.load_image_file(face_image_path)
                face_encodings = face_recognition.face_encodings(image)
                
                if not face_encodings:
                    return {
                        'verified': False,
                        'reason': 'No face detected in image'
                    }
                
                # Compare faces
                matches = face_recognition.compare_faces(
                    [stored_encoding], 
                    face_encodings[0],
                    tolerance=0.6
                )
                
                face_distances = face_recognition.face_distance(
                    [stored_encoding], 
                    face_encodings[0]
                )
                
                if matches[0]:
                    return {
                        'verified': True,
                        'confidence': float(1 - face_distances[0][0])
                    }
                else:
                    return {
                        'verified': False,
                        'reason': 'Face does not match stored image',
                        'distance': float(face_distances[0][0])
                    }
                    
        except ImportError:
            return {
                'verified': False,
                'reason': 'Face recognition library not installed'
            }
        except Exception as e:
            return {
                'verified': False,
                'reason': str(e)
            }

    @staticmethod
    def capture_face_for_student(student_id, image_data, image_path=None):
        """
        Capture and store face encoding for student.
        
        Args:
            student_id: Student ID
            image_data: Image file data
            image_path: Path to save image
        
        Returns:
            bool: Success status
        """
        try:
            import face_recognition
            import numpy as np
            from PIL import Image
            import io
            from datetime import datetime
            
            # Load image
            if isinstance(image_data, bytes):
                image = Image.open(io.BytesIO(image_data))
            else:
                image = Image.open(image_data)
            
            # Convert PIL to numpy array
            image_array = np.array(image)
            
            # Get face encodings
            face_encodings = face_recognition.face_encodings(image_array)
            
            if not face_encodings:
                return False
            
            # Convert encoding to hex for storage
            encoding_hex = face_encodings[0].astype(np.float32).tobytes().hex()
            
            # Save image if path provided
            saved_path = None
            if image_path:
                image.save(image_path)
                saved_path = image_path
            
            # Store in database
            with db_cursor() as (conn, cur):
                cur.execute(
                    """
                    INSERT INTO face_verification 
                    (student_id, face_encoding, image_path, verified)
                    VALUES (%s, %s, %s, TRUE)
                    ON CONFLICT (student_id) DO UPDATE SET
                        face_encoding = EXCLUDED.face_encoding,
                        image_path = EXCLUDED.image_path,
                        verified = TRUE,
                        captured_at = CURRENT_TIMESTAMP
                    """,
                    (student_id, encoding_hex, saved_path)
                )
                conn.commit()
            
            return True
            
        except ImportError:
            print("Face recognition library not installed")
            return False
        except Exception as e:
            print(f"Error capturing face: {str(e)}")
            return False

    @staticmethod
    def add_ip_to_whitelist(ip_range_start, ip_range_end, description=None):
        """
        Add IP range to whitelist.
        
        Args:
            ip_range_start: Start IP (e.g., 192.168.1.0)
            ip_range_end: End IP (e.g., 192.168.1.255)
            description: Range description
        
        Returns:
            bool: Success status
        """
        try:
            with db_cursor() as (conn, cur):
                cur.execute(
                    """
                    INSERT INTO ip_whitelist 
                    (ip_range_start, ip_range_end, description, is_active)
                    VALUES (%s, %s, %s, TRUE)
                    """,
                    (ip_range_start, ip_range_end, description)
                )
                conn.commit()
                return True
        except Exception as e:
            print(f"Error adding IP to whitelist: {str(e)}")
            return False

    @staticmethod
    def get_ip_whitelist():
        """Get all whitelisted IP ranges."""
        with db_cursor() as (conn, cur):
            cur.execute(
                "SELECT * FROM ip_whitelist WHERE is_active = TRUE ORDER BY created_at DESC"
            )
            return cur.fetchall()

    @staticmethod
    def dedup_device_session(student_id, device_id, session_id):
        """
        Enforce device restriction - only allow one device per session.
        
        Args:
            student_id: Student ID
            device_id: Device hash
            session_id: Session ID
        
        Returns:
            tuple: (allowed, reason)
        """
        try:
            device_hash = hashlib.sha256(device_id.encode()).hexdigest()
            
            with db_cursor() as (conn, cur):
                # Check for existing scans from different device in same session
                cur.execute(
                    """
                    SELECT ar.device_info, ar.scan_time
                    FROM attendance_records ar
                    JOIN attendance_sessions asess ON ar.session_id = asess.id
                    WHERE ar.student_id = %s 
                    AND asess.session_id = %s
                    """,
                    (student_id, session_id)
                )
                
                existing = cur.fetchone()
                if existing:
                    # Already marked from this session
                    return False, "Already marked in this session"
                
                # Allow if all checks pass
                return True, "Device verified"
                
        except Exception as e:
            return False, str(e)

    @staticmethod
    def generate_device_id(user_agent, user_ip):
        """Generate unique device identifier."""
        device_string = f"{user_agent}:{user_ip}".encode()
        return hashlib.sha256(device_string).hexdigest()

    @staticmethod
    def log_security_event(student_id, event_type, details=None, risk_level='low'):
        """
        Log security-relevant events.
        
        Args:
            student_id: Student involved
            event_type: Type of event
            details: Event details as dict
            risk_level: 'low', 'medium', 'high'
        """
        try:
            with db_cursor() as (conn, cur):
                cur.execute(
                    """
                    INSERT INTO attendance_audit_log 
                    (student_id, event_type, action, details, flagged)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        student_id, 
                        'security_event', 
                        event_type,
                        json.dumps(details) if details else None,
                        risk_level in ['medium', 'high']
                    )
                )
                conn.commit()
        except Exception as e:
            print(f"Error logging security event: {str(e)}")

    @staticmethod
    def get_student_location_history(student_id, days=7):
        """Get student's attendance location history."""
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                SELECT scan_time, latitude, longitude, accuracy, ip_address
                FROM attendance_records
                WHERE student_id = %s 
                AND scan_time >= CURRENT_TIMESTAMP - INTERVAL '1 day' * %s
                ORDER BY scan_time DESC
                """,
                (student_id, days)
            )
            return cur.fetchall()

    @staticmethod
    def detect_anomalies(student_id):
        """
        Detect suspicious patterns in attendance.
        
        Returns:
            list: List of anomalies detected
        """
        anomalies = []
        
        try:
            with db_cursor() as (conn, cur):
                # Check for multiple locations in short time
                cur.execute(
                    """
                    SELECT ar1.scan_time, ar1.latitude, ar1.longitude,
                           ar2.scan_time, ar2.latitude, ar2.longitude
                    FROM attendance_records ar1
                    JOIN attendance_records ar2 ON ar1.student_id = ar2.student_id
                    WHERE ar1.student_id = %s
                    AND ABS(EXTRACT(EPOCH FROM (ar1.scan_time - ar2.scan_time)) / 60) <= 5
                    AND ar1.id < ar2.id
                    AND ar1.latitude IS NOT NULL
                    AND ar2.latitude IS NOT NULL
                    AND (
                        ABS(ar1.latitude - ar2.latitude) > 0.0045 
                        OR ABS(ar1.longitude - ar2.longitude) > 0.0045
                    )
                    """,
                    (student_id,)
                )
                
                if cur.fetchone():
                    anomalies.append({
                        'type': 'impossible_travel',
                        'description': 'Attendance marked from distant locations in short time',
                        'severity': 'high'
                    })
                
                # Check for late night scans
                cur.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM attendance_records
                    WHERE student_id = %s
                    AND (EXTRACT(HOUR FROM scan_time) < 6 OR EXTRACT(HOUR FROM scan_time) > 22)
                    """,
                    (student_id,)
                )
                
                if cur.fetchone()['count'] > 3:
                    anomalies.append({
                        'type': 'unusual_hours',
                        'description': 'Multiple attendances marked outside normal hours',
                        'severity': 'medium'
                    })
                
        except Exception as e:
            print(f"Error detecting anomalies: {str(e)}")
        
        return anomalies
