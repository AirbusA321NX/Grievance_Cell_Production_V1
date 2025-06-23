# Grievance Cell System

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Architecture & Technologies](#architecture--technologies)
4. [Installation & Setup](#installation--setup)
5. [Authentication & Authorization](#authentication--authorization)
6. [API Endpoints](#api-endpoints)

   * Authentication
   * Users
   * Departments
   * Grievances
   * Comments
7. [Database Schema & Table Attributes](#database-schema--table-attributes)
8. [CRUD Operations](#crud-operations)
9. [Usage Examples](#usage-examples)
10. [Contributing](#contributing)
11. [License](#license)

---

## Overview

The Grievance Cell System is a modular, FastAPI-based backend application designed to streamline grievance management within organizations. It allows users to raise issues, employees to address them, and administrators to oversee the entire workflow—all secured via JWT Bearer authentication and role-based access control.

---

## Features

* **Secure Authentication**: JWT-based signup and login.
* **Role-Based Access Control**: Four roles (`user`, `employee`, `admin`, `super_admin`) with distinct permissions.
* **Hierarchical Entities**: Users belong to Departments. Grievances link to both Users and Departments.
* **Automated Load Balancing**: Pending grievances auto-assigned evenly across employees.
* **Ticketing**: Each grievance gets a unique UUID ticket.
* **Timestamps & Auditing**: Creation and resolution timestamps, plus `resolved_by` tracking.
* **Comments**: Inline commenting on grievances with user and timestamp metadata.
* **Modular Structure**: Separate folders for each domain (User, Department, Grievances, Comments).

---

## Architecture & Technologies

* **Framework**: FastAPI
* **Authentication**: JWT Bearer via `fastapi.security.HTTPBearer`
* **Database**: SQLite with SQLAlchemy ORM
* **Password Hashing**: Passlib bcrypt scheme
* **API Documentation**: Swagger UI (`/docs`)
* **Code Structure**:

  * `User/` — Models, Schemas, CRUD, APIs
  * `Department/` — Models, Schemas, CRUD, APIs
  * `Grievances/` — Models, Schemas, CRUD, APIs
  * `Comments/` — Models, Schemas, CRUD, APIs
  * `auth.py`, `dependencies.py`, `roles.py`, `database.py`, `main.py`

---

## Installation & Setup

1. **Clone the repo**

   ```bash
   git clone https://github.com/your-org/grievance-cell.git
   cd grievance-cell
   ```
2. **Create Virtual Environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate       # Linux/macOS
   .\.venv\\Scripts\\activate    # Windows PowerShell
   ```
3. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```
4. **Initialize Database**

   ```bash
   uvicorn main:app --reload
   # On startup, tables will auto-create in `grievance.db`
   ```
5. **Access API Docs**
   Navigate to [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## Authentication & Authorization

* **Signup** (`POST /signup`): Register new user.
* **Login** (`POST /login`): Obtain `access_token`.
* **Bearer Token**: Include `Authorization: Bearer <token>` in headers.
* **Roles** enforced via `RoleChecker` dependency.

---

## API Endpoints

### Authentication

```http
POST /signup
POST /login
```

### Users

```http
POST /users/             # Create user (admin+)
GET  /users/             # List users
GET  /users/{id}         # Get user details
PUT  /users/{id}         # Update user (admin)
DELETE /users/{id}       # Delete user (admin)
GET  /users/me           # Get own profile
```

### Departments

```http
POST   /departments/     # Create department (admin+)
GET    /departments/     # List departments
PUT    /departments/{id} # Update department (admin)
DELETE /departments/{id} # Delete department (admin)
```

### Grievances

```http
POST   /grievances/               # Create grievance (user)
GET    /grievances/me             # List own grievances
GET    /grievances/assigned       # List assigned (employee)
GET    /grievances/               # List all (admin+)
GET    /grievances/{id}           # Get specific grievance
PUT    /grievances/{id}           # Update status (employee/admin)
POST   /grievances/{id}/resolve   # Resolve grievance
DELETE /grievances/{id}           # Delete grievance (admin+)
POST   /grievances/assign         # Auto-assign pending grievances (admin+)
```

### Comments

```http
POST   /comments/                       # Add comment
GET    /comments/grievance/{id}        # List comments for grievance
DELETE /comments/{id}                  # Delete comment (owner/admin)
```

---

## Database Schema & Table Attributes

### `users`

* `id`: Integer PK
* `email`: String, unique
* `password`: String, hashed
* `role`: Enum(`user`, `employee`, `admin`, `super_admin`)
* `department_id`: FK → `departments.id`

### `departments`

* `id`: Integer PK
* `name`: String, unique

### `grievances`

* `id`: Integer PK
* `ticket_id`: UUID String
* `title`: String
* `description`: Text
* `status`: Enum(`pending`, `resolved`, `not_resolved`)
* `created_at`: DateTime
* `resolved_at`: DateTime nullable
* `user_id`: FK → `users.id`
* `department_id`: FK → `departments.id`
* `assigned_to`: FK → `users.id` (employee)
* `resolved_by`: FK → `users.id`

### `comments`

* `id`: Integer PK
* `grievance_id`: FK → `grievances.id`
* `user_id`: FK → `users.id`
* `content`: Text
* `timestamp`: DateTime

---

## CRUD Operations (Detailed)

### Create

* **Users**: `db.add()`, `db.commit()`, `db.refresh()`
* **Departments**: Similar flow
* **Grievances**: Auto-generate `ticket_id`, default `status="pending"`
* **Comments**: Attach to grievance + timestamp

### Read

* `.filter()` and `.all()` for lists
* `.filter().first()` for single

### Update

* Mutate ORM object fields
* `db.commit()` to persist

### Delete

* `db.delete(obj)` + `db.commit()`

---

## Usage Examples

1. **Signup & Login**

   ```bash
   curl -X POST /signup -d '{"email":"a@b.com","password":"pwd","role":"user"}'
   curl -X POST /login -d 'username=a@b.com&password=pwd'
   ```
2. **Create Department**

   ```bash
   curl -X POST /departments/ -H "Authorization: Bearer <token>" -d '{"name":"IT"}'
   ```
3. **Raise Grievance**

   ```bash
   curl -X POST /grievances/ -H "Authorization: Bearer <token>" -d '{"title":"Issue","description":"Desc","department_id":1}'
   ```

---

## Contributing

* Fork repository
* Create feature branch
* Run tests & linting
* Submit PR with clear description

---
