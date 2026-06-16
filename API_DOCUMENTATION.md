# AI Resume Parser - API Documentation

## Overview

The AI Resume Parser now includes comprehensive authentication and token-based API access. This allows programmatic access to the resume parsing functionality.

## Authentication

### Web Interface
- Register a new account at `/register`
- Log in at `/login`
- Access your profile at `/profile` to manage API tokens

### API Authentication
All API endpoints require a Bearer token in the `Authorization` header.

```bash
Authorization: Bearer <YOUR_API_TOKEN>
```

## Getting Your API Token

1. Log in to the web interface
2. Navigate to your profile page (`/profile`)
3. Scroll to "API Tokens" section
4. Click "Generate Token" and select expiration period
5. Copy the generated token (store it securely - you won't see it again)

## API Endpoints

### 1. Parse Resume
**POST** `/api/parse`

Upload a PDF resume for parsing.

**Headers:**
```
Authorization: Bearer <YOUR_API_TOKEN>
Content-Type: multipart/form-data
```

**Parameters:**
- `resume` (file, required): PDF resume file

**Response (201):**
```json
{
  "resume_id": 1,
  "filename": "resume.pdf",
  "full_name": "John Doe",
  "email": "john@example.com",
  "phone": "+1-234-567-8900",
  "skills": ["Python", "React", "SQL"],
  "education": ["BS Computer Science - University of X"],
  "experience": ["Senior Software Engineer - Company Y (2020-2023)"],
  "certifications": ["AWS Certified Solutions Architect"],
  "score": {
    "total": 85,
    "breakdown": {...}
  },
  "recommendations": ["Add more specific metrics to experience"]
}
```

**Example:**
```bash
curl -X POST http://localhost:5000/api/parse \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "resume=@resume.pdf"
```

### 2. Get Resume Details
**GET** `/api/resume/<resume_id>`

Retrieve details of a previously parsed resume.

**Headers:**
```
Authorization: Bearer <YOUR_API_TOKEN>
```

**Response (200):**
```json
{
  "resume_id": 1,
  "filename": "resume.pdf",
  "created_at": "2026-06-16T17:31:41",
  ...
}
```

**Example:**
```bash
curl http://localhost:5000/api/resume/1 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. List User Resumes
**GET** `/api/resumes`

Get a list of all resumes parsed by the authenticated user.

**Headers:**
```
Authorization: Bearer <YOUR_API_TOKEN>
```

**Query Parameters:**
- `limit` (optional): Maximum number of resumes to return (default: 10)

**Response (200):**
```json
{
  "resumes": [
    {
      "rank": 1,
      "id": 3,
      "filename": "resume1.pdf",
      "name": "Jane Doe",
      "score": 90,
      "created_at": "2026-06-16T17:31:41"
    },
    ...
  ],
  "total": 1
}
```

**Example:**
```bash
curl "http://localhost:5000/api/resumes?limit=20" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 4. Get Analytics
**GET** `/api/analytics`

Returns dashboard totals and score-trend data for the authenticated user.

**Headers:**
```
Authorization: Bearer <YOUR_API_TOKEN>
```

**Example:**
```bash
curl http://localhost:5000/api/analytics \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Token Management

### Generate Token (Web)
Navigate to your profile page to generate new tokens with custom expiration periods (1-365 days).

### Revoke Token (Web)
- Individual tokens can be revoked from the profile page
- All tokens can be revoked at once using the "Revoke All Tokens" button

### Token Expiration
- Tokens expire after the specified period
- You'll need to generate a new token when your current one expires
- Expired tokens will return a 401 Unauthorized response

## Error Responses

### 400 Bad Request
```json
{
  "error": "Upload a PDF file using the 'resume' field."
}
```

### 401 Unauthorized
```json
{
  "error": "API token required"
}
```

```json
{
  "error": "Invalid or expired token"
}
```

### 404 Not Found
```json
{
  "error": "Resume not found"
}
```

## Rate Limiting

Currently no rate limiting is implemented. Please use the API responsibly.

## Python Example

```python
import requests

BASE_URL = "http://localhost:5000"
API_TOKEN = "your_api_token_here"

headers = {
    "Authorization": f"Bearer {API_TOKEN}"
}

# Parse a resume
with open("resume.pdf", "rb") as f:
    response = requests.post(
        f"{BASE_URL}/api/parse",
        headers=headers,
        files={"resume": f}
    )
    parsed = response.json()
    print(f"Resume ID: {parsed['resume_id']}")
    print(f"Score: {parsed['score']['total']}/100")

# List all resumes
response = requests.get(
    f"{BASE_URL}/api/resumes?limit=10",
    headers=headers
)
resumes = response.json()
print(f"Total resumes: {resumes['total']}")

# Get specific resume
response = requests.get(
    f"{BASE_URL}/api/resume/{parsed['resume_id']}",
    headers=headers
)
detail = response.json()
print(f"Candidate: {detail['full_name']}")
```

## JavaScript Example

```javascript
const API_TOKEN = "your_api_token_here";
const BASE_URL = "http://localhost:5000";

// Parse a resume
async function parseResume(file) {
    const formData = new FormData();
    formData.append("resume", file);
    
    const response = await fetch(`${BASE_URL}/api/parse`, {
        method: "POST",
        headers: {
            "Authorization": `Bearer ${API_TOKEN}`
        },
        body: formData
    });
    
    return await response.json();
}

// List resumes
async function listResumes(limit = 10) {
    const response = await fetch(
        `${BASE_URL}/api/resumes?limit=${limit}`,
        {
            headers: {
                "Authorization": `Bearer ${API_TOKEN}`
            }
        }
    );
    
    return await response.json();
}

// Get resume details
async function getResume(resumeId) {
    const response = await fetch(
        `${BASE_URL}/api/resume/${resumeId}`,
        {
            headers: {
                "Authorization": `Bearer ${API_TOKEN}`
            }
        }
    );
    
    return await response.json();
}
```

## Security Notes

- **Never share your API tokens** - treat them like passwords
- Use HTTPS in production
- Regenerate tokens regularly
- Revoke tokens if they're compromised
- Store tokens in environment variables, not in code

## Support

For issues or questions about the API, check the main project README or contact support.
