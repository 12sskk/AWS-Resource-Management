# AWS-Resource-Management
A fully serverless, centralized platform designed for students and faculty to reserve campus resources like classrooms, laboratories, projectors, and seminar halls. 
## 🚀 Features
- **Capacity-Based Booking**: Book individual seats or items (e.g., 2 chairs out of 50). The system automatically tracks concurrent usage and detects capacity conflicts.
- **Secure Authentication**: Powered by Amazon Cognito with an automated Hosted UI.
- **Role-Based Access Control (RBAC)**:
  - **Admin**: Can register new resources, set capacities, and approve/reject bookings.
  - **Faculty**: Can approve/reject pending student bookings.
  - **Student**: Can browse available resources and submit booking requests (which default to a "Pending" status).
- **Automated Provisioning**: Pre-configured Admin and Faculty accounts are automatically generated during deployment via an AWS Lambda Custom Resource.
- **Dynamic Configuration**: The frontend automatically configures its API and Auth endpoints via a dynamically generated `config.json` hosted on Amazon S3.

## 🏗️ Architecture & Tech Stack
- **Infrastructure as Code**: AWS Cloud Development Kit (CDK) v2 in Python
- **Frontend**: Vanilla HTML/JS hosted on **Amazon S3** (Static Website Hosting over HTTPS)
- **API & Routing**: **Amazon API Gateway**
- **Compute**: **AWS Lambda** (Python 3.9)
- **Database**: **Amazon DynamoDB** (NoSQL)
- **Authentication**: **Amazon Cognito** (User Pools & Identity Provider)
- **Notifications**: **Amazon SNS** (Simple Notification Service)

## 📋 Pre-configured Accounts
During deployment, the following accounts are automatically created and verified. Their permanent password is set to **`Password123!`**:
- **Admin**: `admin@smartcampus.com`
- **Faculty**: `faculty1@smartcampus.com` through `faculty5@smartcampus.com`

*Note: Anyone else who signs up via the login page will automatically be assigned the **Student** role by the backend.*

## 🛠️ Deployment Instructions

### Prerequisites
- [Node.js](https://nodejs.org/) (Required for AWS CDK)
- [Python 3.9+](https://www.python.org/)
- [AWS CLI](https://aws.amazon.com/cli/) configured with your credentials (`aws configure`)

### 1. Install AWS CDK
```bash
npm install -g aws-cdk
```

### 2. Setup Python Environment
```bash
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Deploy to AWS
```bash
# Bootstrap the environment (only required once per AWS account/region)
cdk bootstrap

# Deploy the stack
cdk deploy
```

### 4. Access the Application
Once the deployment successfully completes, look at the **Outputs** in your terminal. 
Copy the URL labeled **`SmartCampusStack.FrontendUrl`** and open it in your web browser. Click **Login** and use the pre-configured Admin credentials to start registering campus resources!

## 🧹 Cleanup
To avoid incurring future AWS charges, you can destroy all resources by running:
```bash
cdk destroy
```
