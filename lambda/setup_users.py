import boto3
import os

cognito = boto3.client('cognito-idp')
USER_POOL_ID = os.environ['USER_POOL_ID']
DEFAULT_PASSWORD = "Password123!"

USERS = [
    'admin@smartcampus.com',
    'faculty1@smartcampus.com',
    'faculty2@smartcampus.com',
    'faculty3@smartcampus.com',
    'faculty4@smartcampus.com',
    'faculty5@smartcampus.com'
]

def handler(event, context):
    for email in USERS:
        try:
            # Create user and suppress the welcome email
            cognito.admin_create_user(
                UserPoolId=USER_POOL_ID,
                Username=email,
                UserAttributes=[
                    {'Name': 'email', 'Value': email},
                    {'Name': 'email_verified', 'Value': 'true'}
                ],
                MessageAction='SUPPRESS'
            )
            # Set a permanent password so they don't have to change it on first login
            cognito.admin_set_user_password(
                UserPoolId=USER_POOL_ID,
                Username=email,
                Password=DEFAULT_PASSWORD,
                Permanent=True
            )
            print(f"Created {email}")
        except cognito.exceptions.UsernameExistsException:
            print(f"User {email} already exists. Skipping.")
        except Exception as e:
            print(f"Error creating {email}: {e}")
