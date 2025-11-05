from flask import Flask, jsonify, request
from flask_cors import CORS
import mysql.connector
import pandas as pd
import joblib
import datetime
import logging
import random
from werkzeug.security import generate_password_hash, check_password_hash
from sklearn.ensemble import RandomForestClassifier

app = Flask(__name__)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "12345",
    "database": "Unizulu_db"
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        logger.error(f"Error connecting to MySQL database: {err}")
        return None

# === Machine Learning Model Setup ===
# This section is fine, but you should only run it once to generate the model.
# In a production environment, this part would be separate from the running app.
student_id = [
    '2023461840', '2023114749', '2021126242', '2021256778', '2022912401',
    '2021824658', '2022365656', '2023736558', '2023000827', '2023629957',
    '2023379256', '2021503071', '2022140921', '2023082152', '2021799850',
    '2022916090', '2021098803', '2023655226', '2021551945', '2023553648',
    '2022410504', '2021926763', '2022595898', '2022043110', '2022413944',
    '2023059555', '2022469145', '2022439440', '2022602611', '2022316238',
    '2022709488', '2023159479', '2023619625', '2021150598', '2022001361',
    '2023531755', '2022984648', '2023461633', '2021284942', '2022330230',
    '2022012162', '2022787706', '2021171493', '2021237612', '2021848723',
    '2022863229', '2022100425', '2023197285', '2022082815'
]
num_students = len(student_id)
attendance_rate = [random.uniform(20.0, 100.0) for _ in range(num_students)]
assignment_avg = [random.uniform(30.0, 100.0) for _ in range(num_students)]
test_score = [random.uniform(20.0, 100.0) for _ in range(num_students)]
lms_activity = [random.uniform(10.0, 150.0) for _ in range(num_students)]
risk_levels = ['Low', 'Medium', 'High']
risk_level = [random.choice(risk_levels) for _ in range(num_students)]
data = pd.DataFrame({
    'student_id': student_id,
    'attendance_rate': attendance_rate,
    'assignment_avg': assignment_avg,
    'test_score': test_score,
    'lms_activity': lms_activity,
    'risk_level': risk_level
})
X = data[['attendance_rate', 'assignment_avg', 'test_score', 'lms_activity']]
y = data['risk_level']
model = RandomForestClassifier()
model.fit(X, y)
joblib.dump(model, 'student_risk_model.pkl')
logger.info("Machine learning model trained and saved.")
try:
    model = joblib.load('student_risk_model.pkl')
    logger.info("Machine learning model loaded successfully.")
except FileNotFoundError:
    logger.error("Model file 'student_risk_model.pkl' not found. Please run the model training section.")
    model = None

def calculate_risk_for_student(student_id):
    """
    Calculate and update risk level for a student based on their performance data
    """
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor(dictionary=True)
        
        # Get performance data for the student
        cursor.execute("""
            SELECT subject_code, subject_name, mark, max_mark, grade 
            FROM performance 
            WHERE student_id = %s
        """, (student_id,))
        performance_data = cursor.fetchall()
        
        if not performance_data:
            # No performance data - set to "No Data"
            risk_level = "No Data"
            recommendation = "No performance data found for this student."
            average_percentage = 0
        else:
            # Calculate average percentage
            total_percentage = 0
            for record in performance_data:
                percentage = (record['mark'] / record['max_mark']) * 100
                total_percentage += percentage
            
            average_percentage = total_percentage / len(performance_data)
            
            # Determine risk level based on average percentage
            if average_percentage >= 75:
                risk_level = "Low"
                recommendation = "Student is performing excellently."
            elif average_percentage >= 60:
                risk_level = "Medium"
                recommendation = "Student is performing adequately but could benefit from additional support."
            elif average_percentage >= 50:
                risk_level = "High"
                recommendation = "Student is at risk of academic failure."
            else:
                risk_level = "Very High"
                recommendation = "Student is in critical academic danger."
        
        # Update risk_predictions table
        cursor.execute("""
            INSERT INTO risk_predictions (student_id, risk_level, prediction_date, recommendation, risk_score)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                risk_level = VALUES(risk_level),
                prediction_date = VALUES(prediction_date),
                recommendation = VALUES(recommendation),
                risk_score = VALUES(risk_score)
        """, (student_id, risk_level, datetime.datetime.now().date(), recommendation, average_percentage))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "risk_level": risk_level,
            "average_percentage": round(average_percentage, 2),
            "recommendation": recommendation
        }
        
    except Exception as e:
        logger.error(f"Error calculating risk for student {student_id}: {e}")
        return None

@app.route('/')
def home():
    return 'Welcome to the Student Academic Risk Prediction & Intervention Platform'

# === LOGIN ENDPOINT ===
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Email/username and password required.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'message': 'Database connection error.'}), 500

    cursor = conn.cursor(dictionary=True)
    user = None
    role = None
    password_column = None

    try:
        # Check Lecturers table
        cursor.execute("SELECT * FROM Lecturers WHERE email = %s", (username,))
        lecturer = cursor.fetchone()
        if lecturer:
            user = lecturer
            role = 'lecturer'
            password_column = 'password'

        # If not found, check Admin table
        if not user:
            cursor.execute("SELECT * FROM Administrators WHERE email = %s", (username,))
            admin = cursor.fetchone()
            if admin:
                user = admin
                role = 'admin'
                password_column = 'password'

        # If not found, check Students table
        if not user:
            cursor.execute("SELECT * FROM students WHERE student_id = %s OR email = %s", (username, username))
            student = cursor.fetchone()
            if student:
                user = student
                role = 'student'
                password_column = 'password_hash'

        # Check password
        if user:
            stored_password = user.get(password_column)
            if stored_password and (stored_password == password or check_password_hash(stored_password, password)):
                if role == 'student':
                    return jsonify({
                        'message': 'Login successful',
                        'user_id': user['student_id'],
                        'first_name': user['first_name'],
                        'role': role
                    })
                else:
                    return jsonify({
                        'message': 'Login successful',
                        'user_id': user.get('lecturer_id') or user.get('admin_id'),
                        'full_name': user.get('full_name'),
                        'role': role
                    })
            else:
                return jsonify({'message': 'Invalid credentials.'}), 401
        else:
            return jsonify({'message': 'Invalid credentials.'}), 401

    except mysql.connector.Error as err:
        logger.error(f"Database error during login: {err}")
        return jsonify({'message': 'Database error occurred.'}), 500
    except KeyError as e:
        logger.error(f"Missing key in database result: {e}")
        return jsonify({'message': f"Internal server error: Missing key {e} in database result."}), 500
    finally:
        cursor.close()
        conn.close()

# === FIXED RISK CALCULATION ENDPOINT ===
@app.route('/api/calculate_risk/<string:student_id>', methods=['GET'])
def calculate_risk(student_id):
    """
    Calculate academic risk based on performance data
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection error"}), 500
            
        cursor = conn.cursor(dictionary=True)
        
        # Check if student exists
        cursor.execute("SELECT student_id, first_name, last_name FROM students WHERE student_id = %s", (student_id,))
        student = cursor.fetchone()
        
        if not student:
            return jsonify({"error": "Student not found."}), 404

        # Get performance data for the student
        cursor.execute("""
            SELECT subject_code, subject_name, mark, max_mark, grade 
            FROM performance 
            WHERE student_id = %s
        """, (student_id,))
        performance_data = cursor.fetchall()
        
        if not performance_data:
            return jsonify({
                "student_id": student_id,
                "first_name": student['first_name'],
                "last_name": student['last_name'],
                "risk_level": "No Data",
                "recommendation": "No performance data found for this student. Please add performance records to assess risk.",
                "average_percentage": 0,
                "performance_count": 0
            })

        # Calculate average percentage
        total_percentage = 0
        for record in performance_data:
            percentage = (record['mark'] / record['max_mark']) * 100
            total_percentage += percentage
        
        average_percentage = total_percentage / len(performance_data)
        
        # Determine risk level based on average percentage
        if average_percentage >= 75:
            risk_level = "Low"
            recommendation = "Student is performing excellently. Continue current support and consider advanced opportunities."
        elif average_percentage >= 60:
            risk_level = "Medium"
            recommendation = "Student is performing adequately but could benefit from additional support and monitoring."
        elif average_percentage >= 50:
            risk_level = "High"
            recommendation = "Student is at risk of academic failure. Implement immediate intervention strategies."
        else:
            risk_level = "Very High"
            recommendation = "Student is in critical academic danger. Urgent and comprehensive intervention required."
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "student_id": student_id,
            "first_name": student['first_name'],
            "last_name": student['last_name'],
            "risk_level": risk_level,
            "recommendation": recommendation,
            "average_percentage": round(average_percentage, 2),
            "performance_count": len(performance_data),
            "performance_data": performance_data
        })
        
    except Exception as e:
        logger.error(f"Error calculating risk for student {student_id}: {e}")
        return jsonify({"error": "Failed to calculate risk"}), 500

# === PERFORMANCE MANAGEMENT ENDPOINTS ===
@app.route('/api/performance', methods=['GET'])
def get_all_performance():
    """
    Get all performance records for all students
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection error"}), 500
            
        cursor = conn.cursor(dictionary=True)
        
        query = """
        SELECT 
            p.performance_id,
            p.student_id,
            s.first_name,
            s.last_name,
            s.program,
            p.subject_code,
            p.subject_name,
            p.mark,
            p.max_mark,
            ROUND((p.mark / p.max_mark) * 100, 2) as percentage,
            p.grade,
            p.assessment_type,
            p.assessment_date,
            p.semester,
            p.academic_year,
            p.lecturer_id,
            l.full_name as lecturer_name
        FROM performance p
        LEFT JOIN students s ON p.student_id = s.student_id
        LEFT JOIN Lecturers l ON p.lecturer_id = l.lecturer_id
        ORDER BY p.academic_year DESC, p.semester, s.last_name, s.first_name
        """
        
        cursor.execute(query)
        performance_data = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify(performance_data), 200
        
    except Exception as e:
        logger.error(f"Error fetching performance data: {e}")
        return jsonify({"error": "Failed to fetch performance data"}), 500

@app.route('/api/performance/student/<string:student_id>', methods=['GET'])
def get_student_performance(student_id):
    """
    Get performance records for a specific student
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection error"}), 500
            
        cursor = conn.cursor(dictionary=True)
        
        query = """
        SELECT 
            p.performance_id,
            p.student_id,
            s.first_name,
            s.last_name,
            s.program,
            p.subject_code,
            p.subject_name,
            p.mark,
            p.max_mark,
            ROUND((p.mark / p.max_mark) * 100, 2) as percentage,
            p.grade,
            p.assessment_type,
            p.assessment_date,
            p.semester,
            p.academic_year,
            p.lecturer_id,
            l.full_name as lecturer_name
        FROM performance p
        LEFT JOIN students s ON p.student_id = s.student_id
        LEFT JOIN Lecturers l ON p.lecturer_id = l.lecturer_id
        WHERE p.student_id = %s
        ORDER BY p.academic_year DESC, p.semester, p.subject_code
        """
        
        cursor.execute(query, (student_id,))
        performance_data = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify(performance_data), 200
        
    except Exception as e:
        logger.error(f"Error fetching performance data for student {student_id}: {e}")
        return jsonify({"error": "Failed to fetch student performance data"}), 500

@app.route('/api/performance', methods=['POST'])
def add_performance():
    """
    Add a new performance record
    """
    try:
        data = request.get_json()
        
        required_fields = ['student_id', 'subject_code', 'subject_name', 'mark', 'max_mark', 'assessment_type']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Calculate grade based on percentage
        percentage = (data['mark'] / data['max_mark']) * 100
        if percentage >= 75:
            grade = 'A'
        elif percentage >= 70:
            grade = 'B'
        elif percentage >= 60:
            grade = 'C'
        elif percentage >= 50:
            grade = 'D'
        else:
            grade = 'F'
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection error"}), 500
            
        cursor = conn.cursor()
        
        insert_query = """
        INSERT INTO performance (
            student_id, subject_code, subject_name, mark, max_mark, grade,
            assessment_type, assessment_date, semester, academic_year, lecturer_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(insert_query, (
            data['student_id'],
            data['subject_code'],
            data['subject_name'],
            data['mark'],
            data['max_mark'],
            grade,
            data['assessment_type'],
            data.get('assessment_date', datetime.datetime.now().date()),
            data.get('semester', '2'),
            data.get('academic_year', 2024),
            data.get('lecturer_id')
        ))
        
        conn.commit()
        performance_id = cursor.lastrowid
        
        # Automatically calculate and update risk level for this student
        risk_result = calculate_risk_for_student(data['student_id'])
        
        cursor.close()
        conn.close()
        
        logger.info(f"Performance record added for student {data['student_id']} in subject {data['subject_code']}")
        
        response = {
            "message": "Performance record added successfully!",
            "performance_id": performance_id,
            "calculated_grade": grade,
            "percentage": round(percentage, 2)
        }
        
        if risk_result:
            response["risk_update"] = f"Risk level updated to: {risk_result['risk_level']}"
        
        return jsonify(response), 201
        
    except mysql.connector.Error as err:
        logger.error(f"Database error adding performance: {err}")
        return jsonify({"error": f"Database Error: {err.msg}"}), 400
    except Exception as e:
        logger.error(f"Error adding performance record: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/performance/<int:performance_id>', methods=['PUT'])
def update_performance(performance_id):
    """
    Update a performance record
    """
    try:
        data = request.get_json()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection error"}), 500
            
        cursor = conn.cursor(dictionary=True)
        
        # First, get the current record
        cursor.execute("SELECT * FROM performance WHERE performance_id = %s", (performance_id,))
        current_record = cursor.fetchone()
        
        if not current_record:
            return jsonify({"error": "Performance record not found"}), 404
        
        # Calculate new grade if mark or max_mark is being updated
        mark = data.get('mark', current_record['mark'])
        max_mark = data.get('max_mark', current_record['max_mark'])
        percentage = (mark / max_mark) * 100
        
        if percentage >= 75:
            grade = 'A'
        elif percentage >= 70:
            grade = 'B'
        elif percentage >= 60:
            grade = 'C'
        elif percentage >= 50:
            grade = 'D'
        else:
            grade = 'F'
        
        update_query = """
        UPDATE performance 
        SET student_id = %s, subject_code = %s, subject_name = %s, 
            mark = %s, max_mark = %s, grade = %s, assessment_type = %s,
            assessment_date = %s, semester = %s, academic_year = %s, lecturer_id = %s
        WHERE performance_id = %s
        """
        
        cursor.execute(update_query, (
            data.get('student_id', current_record['student_id']),
            data.get('subject_code', current_record['subject_code']),
            data.get('subject_name', current_record['subject_name']),
            mark,
            max_mark,
            grade,
            data.get('assessment_type', current_record['assessment_type']),
            data.get('assessment_date', current_record['assessment_date']),
            data.get('semester', current_record['semester']),
            data.get('academic_year', current_record['academic_year']),
            data.get('lecturer_id', current_record['lecturer_id']),
            performance_id
        ))
        
        conn.commit()
        
        # Automatically calculate and update risk level for this student
        student_id = data.get('student_id', current_record['student_id'])
        risk_result = calculate_risk_for_student(student_id)
        
        cursor.close()
        conn.close()
        
        logger.info(f"Performance record {performance_id} updated successfully")
        
        response = {
            "message": "Performance record updated successfully!",
            "calculated_grade": grade,
            "percentage": round(percentage, 2)
        }
        
        if risk_result:
            response["risk_update"] = f"Risk level updated to: {risk_result['risk_level']}"
        
        return jsonify(response), 200
        
    except mysql.connector.Error as err:
        logger.error(f"Database error updating performance: {err}")
        return jsonify({"error": f"Database Error: {err.msg}"}), 400
    except Exception as e:
        logger.error(f"Error updating performance record: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/performance/<int:performance_id>', methods=['DELETE'])
def delete_performance(performance_id):
    """
    Delete a performance record
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection error"}), 500
            
        cursor = conn.cursor()
        
        # First get the student_id before deleting
        cursor.execute("SELECT student_id FROM performance WHERE performance_id = %s", (performance_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({"error": "Performance record not found"}), 404
        
        student_id = result[0]
        
        cursor.execute("DELETE FROM performance WHERE performance_id = %s", (performance_id,))
        conn.commit()
        
        # Automatically recalculate risk level for this student
        risk_result = calculate_risk_for_student(student_id)
        
        cursor.close()
        conn.close()
        
        logger.info(f"Performance record {performance_id} deleted successfully")
        
        response = {"message": "Performance record deleted successfully!"}
        
        if risk_result:
            response["risk_update"] = f"Risk level recalculated: {risk_result['risk_level']}"
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Error deleting performance record: {e}")
        return jsonify({"error": str(e)}), 500

# === STUDENT DATA ENDPOINTS ===
@app.route('/api/students', methods=['GET'])
def api_students():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                s.student_id,
                s.first_name,
                s.last_name,
                s.program,
                s.last_login, 
                COALESCE(p.risk_level, 'No Data') as risk_level,
                p.prediction_date,
                p.risk_score,
                a.attendance_percentage AS attendance_rate,
                ROUND(AVG(ass.score / ass.max_score) * 100, 2) AS assignment_avg,
                l.lms_activity_score AS lms_activity
            FROM
                students AS s
            LEFT JOIN
                risk_predictions AS p ON s.student_id = p.student_id
            LEFT JOIN
                attendance AS a ON s.student_id = a.student_id
            LEFT JOIN
                assessments AS ass ON s.student_id = ass.student_id
            LEFT JOIN
                lms_activity AS l ON s.student_id = l.student_id
            GROUP BY
                s.student_id, s.first_name, s.last_name,s.program, s.last_login, p.risk_level, p.prediction_date, p.risk_score, a.attendance_percentage, l.lms_activity_score
            ORDER BY
                s.student_id;

        """)
        students_data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(students_data)
    else:
        return jsonify([]), 500

@app.route('/api/add_student', methods=['POST'])
def add_student():
    """Adds a new student to the database."""
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO students (student_id, first_name, last_name, program) VALUES (%s, %s, %s, %s)",
                       (data['student_id'], data['first_name'], data['last_name'], data['program']))
        
        # Initialize risk prediction for new student
        cursor.execute("""
            INSERT INTO risk_predictions (student_id, risk_level, prediction_date, recommendation, risk_score)
            VALUES (%s, 'No Data', %s, 'No performance data available.', 0)
        """, (data['student_id'], datetime.datetime.now().date()))
        
        conn.commit()
        
        # Return success with risk info
        return jsonify({
            "message": "Student added successfully!",
            "risk_level": "No Data",
            "note": "Risk level will be calculated when performance data is added."
        }), 201
    except mysql.connector.Error as err:
        return jsonify({"error": f"Database Error: {err.msg}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/add_lecturer', methods=['POST'])
def add_lecturer():
    """Adds a new lecturer to the database."""
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Lecturers (lecturer_id, full_name, email, password, department) VALUES (%s, %s, %s, %s, %s)",
                       (data['lecturer_id'], data['full_name'], data['email'], data['password'], data['department']))
        conn.commit()
        return jsonify({"message": "Lecturer added successfully!"}), 201
    except mysql.connector.Error as err:
        return jsonify({"error": f"Database Error: {err.msg}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/add_admin', methods=['POST'])
def add_admin():
    """Adds a new admin to the database."""
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Administrators (admin_id, full_name, email, password, role) VALUES (%s, %s, %s, %s, %s)",
                       (data['admin_id'], data['full_name'], data['email'], data['password'], data['role']))
        conn.commit()
        return jsonify({"message": "Admin added successfully!"}), 201
    except mysql.connector.Error as err:
        return jsonify({"error": f"Database Error: {err.msg}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/students/update_program/<string:student_id>', methods=['PUT'])
def update_student_program(student_id):
    """
    Updates a student's program.
    """
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE students SET program = %s WHERE student_id = %s", (data['program'], student_id))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": "Student not found or program not changed."}), 404
        return jsonify({"message": "Student program updated successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/delete_student/<string:student_id>', methods=['DELETE'])
def delete_student(student_id):
    """Deletes a student record and all related records."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Delete from child tables first
        cursor.execute("DELETE FROM assessments WHERE student_id = %s", (student_id,))
        cursor.execute("DELETE FROM attendance WHERE student_id = %s", (student_id,))
        cursor.execute("DELETE FROM performance WHERE student_id = %s", (student_id,))
        cursor.execute("DELETE FROM lms_activity WHERE student_id = %s", (student_id,))
        cursor.execute("DELETE FROM interventions WHERE student_id = %s", (student_id,))
        cursor.execute("DELETE FROM risk_predictions WHERE student_id = %s", (student_id,))  # <-- Add this line
        # Now delete from students
        cursor.execute("DELETE FROM students WHERE student_id = %s", (student_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": "Student not found."}), 404
        return jsonify({"message": "Student deleted successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/delete_lecturer/<string:lecturer_id>', methods=['DELETE'])
def delete_lecturer(lecturer_id):
    """Deletes a lecturer record."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Lecturers WHERE lecturer_id = %s", (lecturer_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": "Lecturer not found."}), 404
        return jsonify({"message": "Lecturer deleted successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/delete_admin/<string:admin_id>', methods=['DELETE'])
def delete_admin(admin_id):
    """Deletes an admin record."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Administrators WHERE admin_id = %s", (admin_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": "Admin not found."}), 404
        return jsonify({"message": "Admin deleted successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/delete_performance/<string:student_id>/<string:subject_code>', methods=['DELETE'])
def delete_performance_by_student_subject(student_id, subject_code):
    """Deletes a performance record for a student and subject."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM performance WHERE student_id = %s AND subject_code = %s", (student_id, subject_code,))
        conn.commit()
        
        # Automatically recalculate risk level
        risk_result = calculate_risk_for_student(student_id)
        
        if cursor.rowcount == 0:
            return jsonify({"error": "Performance record not found."}), 404
        
        response = {"message": "Performance record deleted successfully!"}
        if risk_result:
            response["risk_update"] = f"Risk level recalculated: {risk_result['risk_level']}"
        
        return jsonify(response), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# === DATA MANAGEMENT ENDPOINTS ===
@app.route('/api/attendance', methods=['POST'])
def add_attendance():
    """Adds attendance record."""
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if student exists
        cursor.execute("SELECT student_id FROM students WHERE student_id = %s", (data['student_id'],))
        if not cursor.fetchone():
            return jsonify({"error": "Student not found."}), 404
            
        cursor.execute("""
            INSERT INTO attendance (student_id, course_id, attendance_percentage) 
            VALUES (%s, 1, %s)
            ON DUPLICATE KEY UPDATE attendance_percentage = %s
        """, (data['student_id'], data['attendance_percentage'], data['attendance_percentage']))
        
        conn.commit()
        return jsonify({"message": "Attendance record added/updated successfully!"}), 201
    except mysql.connector.Error as err:
        return jsonify({"error": f"Database Error: {err.msg}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/assessments', methods=['POST'])
def add_assessment():
    """Adds assessment record."""
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if student exists
        cursor.execute("SELECT student_id FROM students WHERE student_id = %s", (data['student_id'],))
        if not cursor.fetchone():
            return jsonify({"error": "Student not found."}), 404
            
        cursor.execute("""
            INSERT INTO assessments (student_id, course_id, assessment_type, score, max_score) 
            VALUES (%s, 1, %s, %s, %s)
        """, (data['student_id'], data['assessment_type'], data['score'], data['max_score']))
        
        conn.commit()
        return jsonify({"message": "Assessment record added successfully!"}), 201
    except mysql.connector.Error as err:
        return jsonify({"error": f"Database Error: {err.msg}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/lms_activity', methods=['POST'])
def add_lms_activity():
    """Adds LMS activity record."""
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if student exists
        cursor.execute("SELECT student_id FROM students WHERE student_id = %s", (data['student_id'],))
        if not cursor.fetchone():
            return jsonify({"error": "Student not found."}), 404
            
        cursor.execute("""
            INSERT INTO lms_activity (student_id, lms_activity_score) 
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE lms_activity_score = %s
        """, (data['student_id'], data['lms_activity_score'], data['lms_activity_score']))
        
        conn.commit()
        return jsonify({"message": "LMS activity record added/updated successfully!"}), 201
    except mysql.connector.Error as err:
        return jsonify({"error": f"Database Error: {err.msg}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# === SEARCH AND NOTIFICATION ENDPOINTS ===
@app.route('/api/search/students', methods=['GET'])
def search_students():
    """
    Search students by ID, name, or program
    """
    search_term = request.args.get('q', '')
    if not search_term:
        return jsonify({"error": "Search term is required"}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection error"}), 500
        
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
        SELECT 
            s.student_id,
            s.first_name,
            s.last_name,
            s.program,
            COALESCE(p.risk_level, 'No Data') as risk_level,
            p.risk_score
        FROM students s
        LEFT JOIN risk_predictions p ON s.student_id = p.student_id
        WHERE s.student_id LIKE %s 
           OR s.first_name LIKE %s 
           OR s.last_name LIKE %s 
           OR s.program LIKE %s
        ORDER BY s.student_id
        LIMIT 50
        """
        
        search_pattern = f"%{search_term}%"
        cursor.execute(query, (search_pattern, search_pattern, search_pattern, search_pattern))
        results = cursor.fetchall()
        
        return jsonify(results), 200
        
    except Exception as e:
        logger.error(f"Error searching students: {e}")
        return jsonify({"error": "Search failed"}), 500
    finally:
        cursor.close()
        conn.close()


# === NOTIFICATIONS ENDPOINT ===
@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    """
    Get notifications/interventions for students
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection error"}), 500
            
        cursor = conn.cursor(dictionary=True)
        
        # Get student ID from query parameter or all notifications
        student_id = request.args.get('student_id')
        
        if student_id:
            cursor.execute("""
                SELECT i.*, s.first_name, s.last_name 
                FROM interventions i 
                JOIN students s ON i.student_id = s.student_id 
                WHERE i.student_id = %s 
                ORDER BY i.intervention_date DESC
            """, (student_id,))
        else:
            cursor.execute("""
                SELECT i.*, s.first_name, s.last_name 
                FROM interventions i 
                JOIN students s ON i.student_id = s.student_id 
                ORDER BY i.intervention_date DESC 
                LIMIT 50
            """)
        
        notifications = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify(notifications), 200
        
    except Exception as e:
        logger.error(f"Error fetching notifications: {e}")
        return jsonify({"error": "Failed to fetch notifications"}), 500

# === CREATE INTERVENTION ENDPOINT ===
@app.route('/api/interventions', methods=['POST'])
def create_intervention():
    """
    Create a new intervention
    """
    try:
        data = request.get_json()
        
        required_fields = ['student_id', 'intervention_type', 'due_date', 'owner']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection error"}), 500
            
        cursor = conn.cursor()
        
        insert_query = """
        INSERT INTO interventions 
        (student_id, intervention_type, intervention_date, due_date, owner, description, outcome)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(insert_query, (
            data['student_id'],
            data['intervention_type'],
            datetime.datetime.now().date(),
            data['due_date'],
            data['owner'],
            data.get('description', ''),
            data.get('outcome', 'Pending')
        ))
        
        conn.commit()
        intervention_id = cursor.lastrowid
        
        cursor.close()
        conn.close()
        
        logger.info(f"Intervention created for student {data['student_id']}: {data['intervention_type']}")
        
        return jsonify({
            "message": "Intervention created successfully!",
            "intervention_id": intervention_id
        }), 201
        
    except mysql.connector.Error as err:
        logger.error(f"Database error creating intervention: {err}")
        return jsonify({"error": f"Database Error: {err.msg}"}), 400
    except Exception as e:
        logger.error(f"Error creating intervention: {e}")
        return jsonify({"error": str(e)}), 500

# === UPLOAD DOCUMENT ENDPOINT ===
@app.route('/api/upload_document', methods=['POST'])
def upload_document():
    """
    Handle Excel file uploads for student data
    """
    try:
        if 'document' not in request.files:
            return jsonify({"error": "No file provided"}), 400
            
        file = request.files['document']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # Check if it's an Excel file
        if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
            return jsonify({"error": "Only Excel files are allowed"}), 400
        
        # For now, we'll just log the upload and return success
        # In a real implementation, we will need to parse the Excel file
        # and insert data into the database
        
        student_number = request.form.get('studentNumber', 'Unknown')
        
        logger.info(f"File uploaded: {file.filename} for student {student_number}")
        
        # 1. Read the Excel file (using pandas or openpyxl)
        # 2. Validate the data
        # 3. Insert into the appropriate tables
        # 4. Return appropriate response
        
        return jsonify({
            "message": f"File '{file.filename}' uploaded successfully. Processing would be implemented here.",
            "filename": file.filename,
            "student_number": student_number
        }), 200
        
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        return jsonify({"error": "Upload failed"}), 500

# === GET STUDENT DETAILS ENDPOINT ===
@app.route('/api/student/<string:student_id>', methods=['GET'])
def get_student_details(student_id):
    """
    Get comprehensive student details
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection error"}), 500
            
        cursor = conn.cursor(dictionary=True)
        
        # Get basic student info
        cursor.execute("""
            SELECT student_id, first_name, last_name, email, program, year_of_study
            FROM students WHERE student_id = %s
        """, (student_id,))
        
        student = cursor.fetchone()
        if not student:
            return jsonify({"error": "Student not found"}), 404
        
        # Get attendance
        cursor.execute("""
            SELECT attendance_percentage 
            FROM attendance 
            WHERE student_id = %s 
            ORDER BY attendance_id DESC 
            LIMIT 1
        """, (student_id,))
        attendance = cursor.fetchone()
        
        # Get LMS activity
        cursor.execute("""
            SELECT lms_activity_score 
            FROM lms_activity 
            WHERE student_id = %s 
            ORDER BY lms_activity_id DESC 
            LIMIT 1
        """, (student_id,))
        lms_activity = cursor.fetchone()
        
        # Get risk prediction
        cursor.execute("""
            SELECT risk_level, risk_score, recommendation, prediction_date
            FROM risk_predictions 
            WHERE student_id = %s 
            ORDER BY prediction_date DESC 
            LIMIT 1
        """, (student_id,))
        risk_prediction = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "student_info": student,
            "attendance": attendance,
            "lms_activity": lms_activity,
            "risk_prediction": risk_prediction
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching student details: {e}")
        return jsonify({"error": "Failed to fetch student details"}), 500

# === GET CLASS ANALYSIS DATA ===
@app.route('/api/analysis/class_trends', methods=['GET'])
def get_class_trends():
    """
    Get data for class analysis and trends
    """
    try:
        module = request.args.get('module', 'all')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection error"}), 500
            
        cursor = conn.cursor(dictionary=True)
        
        # Risk distribution
        cursor.execute("""
            SELECT 
                risk_level,
                COUNT(*) as count
            FROM risk_predictions rp
            JOIN students s ON rp.student_id = s.student_id
            GROUP BY risk_level
        """)
        risk_distribution = cursor.fetchall()
        
        # Attendance trends
        cursor.execute("""
            SELECT 
                AVG(attendance_percentage) as avg_attendance
            FROM attendance
        """)
        attendance_trends = cursor.fetchone()
        
        # Performance by module
        cursor.execute("""
            SELECT 
                subject_code,
                AVG((mark / max_mark) * 100) as avg_percentage,
                COUNT(*) as record_count
            FROM performance
            GROUP BY subject_code
        """)
        performance_by_module = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "risk_distribution": risk_distribution,
            "attendance_trends": attendance_trends,
            "performance_by_module": performance_by_module
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching class trends: {e}")
        return jsonify({"error": "Failed to fetch class trends"}), 500

@app.route('/api/send_notification', methods=['POST'])
def send_notification():
    data = request.json
    student_number = data.get('student_number')
    message_content = data.get('message')

    if not student_number or not message_content:
        return jsonify({'message': 'Student number and message are required'}), 400
    
    # Insert notification into the interventions table
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        insert_query = """
        INSERT INTO interventions (student_id, intervention_type, description, intervention_date)
        VALUES (%s, %s, %s, %s)
        """
        cursor.execute(insert_query, (
            student_number,
            'Notification',
            message_content,
            datetime.datetime.now().date()
        ))
        conn.commit()
        cursor.close()
        conn.close()
        
    return jsonify({'message': f'Notification sent successfully to student {student_number}.'}), 200

# === UPDATE STUDENT LOGIN TIME ===
@app.route('/api/update_student_login/<string:student_id>', methods=['POST'])
def update_student_login(student_id):
    """
    Update student's last login time
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection error"}), 500
            
        cursor = conn.cursor()
        
        # Update last login time
        cursor.execute("""
            UPDATE students 
            SET last_login = %s 
            WHERE student_id = %s
        """, (datetime.datetime.now(), student_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Updated last login for student {student_id}")
        return jsonify({"message": "Login time updated successfully"}), 200
        
    except Exception as e:
        logger.error(f"Error updating student login time: {e}")
        return jsonify({"error": "Failed to update login time"}), 500

# === UPDATE STUDENT RISK CHECK TIME ===
@app.route('/api/update_risk_check/<string:student_id>', methods=['POST'])
def update_risk_check(student_id):
    """
    Update student's last risk check time
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection error"}), 500
            
        cursor = conn.cursor()
        
        # Update last risk check time
        cursor.execute("""
            UPDATE students 
            SET last_risk_check = %s 
            WHERE student_id = %s
        """, (datetime.datetime.now(), student_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Updated last risk check for student {student_id}")
        return jsonify({"message": "Risk check time updated successfully"}), 200
        
    except Exception as e:
        logger.error(f"Error updating student risk check time: {e}")
        return jsonify({"error": "Failed to update risk check time"}), 500

# === GET STUDENT ACTIVITY ===
@app.route('/api/student_activity/<string:student_id>', methods=['GET'])
def get_student_activity(student_id):
    """
    Get student's last login and risk check times
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection error"}), 500
            
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                student_id,
                first_name,
                last_name,
                last_login,
                last_risk_check
            FROM students 
            WHERE student_id = %s
        """, (student_id,))
        
        student_activity = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not student_activity:
            return jsonify({"error": "Student not found"}), 404
            
        return jsonify(student_activity), 200
        
    except Exception as e:
        logger.error(f"Error fetching student activity: {e}")
        return jsonify({"error": "Failed to fetch student activity"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)