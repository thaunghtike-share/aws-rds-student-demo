# AWS RDS MySQL – Student Registration Demo

A small, beginner-friendly Flask application that demonstrates an Ubuntu EC2 instance connecting to a private Amazon RDS for MySQL database. The app creates its database and table automatically, registers students, and reads the saved records back from RDS.

This project intentionally uses Flask's built-in server for a temporary, access-restricted classroom lab. It is not a production deployment pattern.

## What the application demonstrates

- EC2-to-RDS connectivity through an RDS endpoint
- Idempotent database and table creation at application startup
- Parameterized SQL inserts and queries with PyMySQL
- Duplicate email prevention with a MySQL `UNIQUE` constraint
- Persistent student records loaded newest-first

## Architecture and security groups

Use an EC2 instance and RDS database in the same VPC:

```text
Instructor computer
    |
    | SSH 22 and HTTP 5000 (instructor public IP only)
    v
Ubuntu EC2 in a public subnet
    |
    | MySQL 3306 (private VPC traffic)
    v
Amazon RDS MySQL in private DB subnets
```

Configure the security groups as follows:

1. **EC2 security group:** allow inbound TCP 22 and TCP 5000 from your public IP address only.
2. **RDS security group:** allow inbound TCP 3306 with the EC2 security group as the source. Do not use `0.0.0.0/0`.
3. Set the RDS database to **Public access: No**. The EC2 instance reaches it over the private VPC network.

## RDS preparation

Create an Amazon RDS for MySQL database in private DB subnets. For this short educational lab, use the RDS master user (for example, `admin`). Record:

- The RDS endpoint (do not add `http://`)
- The port, normally `3306`
- The master username and password

The master user needs permission to run `CREATE DATABASE`, `CREATE TABLE`, `SELECT`, and `INSERT`. The application creates the configured database and `students` table; no `init.sql` file is needed.

## Deploy on Ubuntu EC2

### 1. Connect and install Python tools

```bash
ssh -i your-key.pem ubuntu@EC2_PUBLIC_IP
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git
```

### 2. Clone the repository

Replace the example URL with the URL containing this project:

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY/aws-rds-student-demo
```

If this folder is the repository root, change directly into the cloned repository instead.

### 3. Create a virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The PyMySQL RSA extra installs the cryptography support required by the
`caching_sha2_password` authentication method used by current MySQL versions.

### 4. Configure environment variables

```bash
cp .env.example .env
nano .env
```

Set the values for your RDS database:

```dotenv
DB_HOST=my-database.abc123.ap-southeast-1.rds.amazonaws.com
DB_PORT=3306
DB_NAME=demo_db
DB_USER=admin
DB_PASSWORD=replace-with-your-rds-password

FLASK_HOST=0.0.0.0
FLASK_PORT=5000
```

Do not commit `.env`. It is excluded by `.gitignore`.

### 5. Start the application

```bash
python3 app.py
```

At startup, the application:

1. Connects to the RDS MySQL server without selecting a database.
2. Runs `CREATE DATABASE IF NOT EXISTS` for the validated `DB_NAME`.
3. Connects to that database.
4. Runs `CREATE TABLE IF NOT EXISTS` for the `students` table.
5. Starts Flask on port 5000 with debug mode disabled.

Both SQL operations are idempotent. Restarting the app preserves existing records.

### 6. Test the demo

Open this URL in a browser:

```text
http://EC2_PUBLIC_IP:5000
```

Confirm the database status is connected, register a student, and check that the new row appears in the table. Refresh the page to verify that the record persists in RDS. Registering the same email again shows a friendly duplicate warning.

Stop the application with `Ctrl+C` when the lab is finished.

## SSL/TLS note for this simplified lab

The app uses PyMySQL's default connection behavior and does not provide a CA certificate or additional SSL options. Therefore, this simplified connection does **not guarantee TLS encryption**. The RDS configuration must permit the client's default connection behavior.

Do not disable `require_secure_transport`, weaken certificate checks, or change an RDS parameter group automatically to make the demo connect. If the RDS instance requires TLS, this app will report a connection/setup error. For a production application—or a course module specifically covering TLS—configure verified TLS using the current Amazon RDS CA bundle and appropriate PyMySQL SSL settings.

## Troubleshooting

### Connection times out

- Confirm EC2 and RDS are in the same VPC and the selected subnets have valid routes.
- Confirm the RDS security group allows inbound TCP 3306 **from the EC2 security group**.
- Check that the RDS instance is in the `Available` state.
- Test name resolution from EC2 with `getent hosts YOUR_RDS_ENDPOINT`.
- Do not make RDS publicly accessible to solve a private connectivity problem.

### Endpoint is incorrect

- Copy the endpoint from **RDS console → Databases → your database → Connectivity & security**.
- Use only the hostname, without `http://`, `https://`, or `:3306`.
- Keep the port in the separate `DB_PORT` variable.

### Access denied or credentials are incorrect

- Verify `DB_USER` and `DB_PASSWORD` in `.env`.
- Remember that the RDS database password is different from the EC2 SSH key.
- If the password contains `#`, keep it as part of the value without adding an inline comment.

### Database creation permission error

- Use the RDS master user (`admin` in this lab).
- Confirm that the user can create databases and tables.
- Ensure `DB_NAME` contains only letters, numbers, and underscores.

### RDS requires SSL/TLS

If RDS enforces secure transport, PyMySQL may report an error such as `Connections using insecure transport are prohibited`. This lab deliberately does not download or configure a CA certificate. Use an RDS setup that permits this lab's client behavior, or extend the lesson with verified TLS configuration. Do not silently disable server-side transport security.

### Port 5000 cannot be reached

- Confirm Flask displays `Running on http://0.0.0.0:5000`.
- Confirm the EC2 security group allows TCP 5000 from your current public IP.
- Confirm `FLASK_HOST=0.0.0.0` and `FLASK_PORT=5000` in `.env`.
- If Ubuntu's firewall is enabled, inspect it with `sudo ufw status`.

### View detailed server-side errors

The browser intentionally shows generic errors so it never exposes credentials or internal exception details. Read the terminal where `python3 app.py` is running for the detailed error needed during setup.

## Project structure

```text
aws-rds-student-demo/
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── templates/
│   └── index.html
└── static/
    └── style.css
```
