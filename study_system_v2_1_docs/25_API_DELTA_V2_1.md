# API Delta — V2.1

## Profile
GET /user-model
PATCH /user-model/preferences

## Questionnaire
POST /onboarding/questions/next
POST /onboarding/answers
GET /onboarding/summary

## Weekly interview
POST /planning/weekly-interview/start
POST /planning/weekly-interview/answer
GET /planning/weekly-interview/{week_start}
POST /planning/weekly-interview/complete

## Behavior
GET /behavior/summary
GET /behavior/features

## State
GET /state/current
POST /state/check-in

## Planning
POST /planning/generate
POST /planning/rebuild
GET /planning/week/{week_start}

## Manual editing
POST /tasks
PATCH /tasks/{id}
DELETE /tasks/{id}
POST /tasks/{id}/move
POST /tasks/{id}/split
POST /tasks/{id}/merge
POST /tasks/{id}/accept-suggestion
POST /tasks/{id}/reject-suggestion

## اصل
API باید تغییرات دستی را صریح ثبت کند و Planner نباید آنها را بی‌اجازه overwrite کند.
