import os
import argparse
from app import send_risk_alert, app, mail
from flask_mail import Message


def build_sample():
    return {
        'studentName': 'Test Student',
        'studentEmail': os.getenv('TEST_RECIPIENT', 'teststudent@example.com'),
        'riskLevel': 'High',
        'alertMessage': 'This is a test alert from automated test script.',
        'recommendations': 'Contact student and follow up.'
    }


def dry_run_print(form_data):
    # Build the same body the app uses so it's representative
    subject = f"Unizulu Risk Alert - {form_data['riskLevel']} Risk Level - {form_data['studentName']}"
    body = f"""
UNIZULU RISK ALERT SYSTEM - NEW ALERT SUBMISSION

STUDENT INFORMATION:
-------------------
Name: {form_data['studentName']}
Email: {form_data.get('studentEmail', 'Not provided')}

RISK ASSESSMENT:
----------------
Risk Level: {form_data['riskLevel']}

ALERT DETAILS:
--------------
{form_data['alertMessage']}

RECOMMENDATIONS & NEXT STEPS:
-----------------------------
{form_data.get('recommendations', 'Not provided')}

---
This alert was submitted through the Unizulu Risk Alert System.
"""

    # Determine recipients like the app does
    student_email = form_data.get('studentEmail', '').strip()
    recipients = []
    to_mail_env = os.getenv('TO_MAIL')

    if student_email and '@' in student_email:
        recipients.append(student_email)

    if to_mail_env and to_mail_env not in recipients:
        recipients.append(to_mail_env)

    print('DRY RUN - Message would be sent with:')
    print('Subject:', subject)
    print('Sender:', app.config.get('MAIL_DEFAULT_SENDER'))
    print('Recipients:', recipients)
    print('Body:')
    print(body)


def main(dry_run=False):
    sample = build_sample()

    if dry_run:
        dry_run_print(sample)
        return

    ok = send_risk_alert(sample)
    print('send_risk_alert returned:', ok)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Print message instead of sending')
    args = parser.parse_args()

    main(dry_run=args.dry_run)
