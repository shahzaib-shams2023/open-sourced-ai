# Workspace Reference Manual

This documentation is loaded automatically by the USTAAD RAG (Retrieval-Augmented Generation) engine to guide agents in conforming to workspace standards.

## 🔑 Authentication Specifications
All API connections require authenticating via a JWT bearer token. 
* **Login Endpoint**: `POST /api/v1/auth/login`
* **Request Format**: JSON body containing exact keys `email` and `password`.
* **Success Payload**: Returns status code `200` with response body:
  ```json
  {
    "status": "success",
    "token": "eyJhbGciOi...",
    "expires_in": 3600
  }
  ```

## 📦 Database Naming Conventions
* **Tables**: Must use snake_case plural naming (e.g. `user_accounts`, `billing_profiles`).
* **Primary Keys**: Always named `id` and must be UUIDv4 values.
* **Timestamps**: Must include `created_at` and `updated_at` with timezones enabled.
