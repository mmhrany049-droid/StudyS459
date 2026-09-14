# API Contract — نسخه ۱

## Auth
POST /auth/login  
POST /auth/logout  
GET /auth/me

## Books
GET /books  
GET /books/{id}  
POST /books/import  
POST /users/me/books/{id}/activate  
DELETE /users/me/books/{id}/activate

## Nodes
GET /books/{id}/nodes  
GET /nodes/{id}/children  
GET /nodes/{id}/parity-state

## Tests
POST /test-sessions  
Body مثال:
{
  "node_id": 123,
  "count": 20,
  "sequence_from": 21,
  "sequence_to": 41,
  "parity": "odd",
  "timed": false
}

GET /test-sessions/{id}  
POST /test-sessions/{id}/answers  
POST /test-sessions/{id}/finish  
GET /questions/{id}/history

## Progress
GET /progress/overview  
GET /progress/books/{id}  
GET /progress/nodes/{id}  
GET /progress/questions/{id}  
GET /analytics/trends  
GET /analytics/weaknesses

## Goals
GET /goals/weeks/{week}  
POST /goals/weeks/{week}  
PATCH /goals/{id}  
GET /goals/{id}/candidate-tasks

## Planner
GET /planner/day/{date}  
GET /planner/week/{week}  
POST /tasks  
PATCH /tasks/{id}  
POST /tasks/{id}/complete  
PUT /planner/placements

## Academic
GET/POST /schedules  
POST /school-day-overrides  
GET/POST /class-sessions  
GET/POST /taught-lessons  
GET/POST /homework  
PATCH /homework/{id}

## Exams
GET/POST /exams  
GET /exams/{id}  
POST /exams/{id}/questions  
GET /exams/{id}/analytics

## Rewards
GET /rewards/summary  
GET /rewards/events  
GET /rewards/badges

## Telegram (اختیاری)
POST /telegram/connect  
PATCH /telegram/settings  
POST /telegram/test-message

## Rule
هیچ endpointی بدون ownership داده را expose نکند.  
برنامه بدون endpointهای Telegram کامل کار می‌کند.
