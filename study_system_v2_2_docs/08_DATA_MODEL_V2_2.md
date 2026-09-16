# مدل داده — دلتا نسخه ۲.۲

## Question bank (گسترش)
- questions: از قبل؛ تأکید روی answer_key و sequence_no
- امکان question بدون answer_key موقت

## Taught
- taught_topics: id, user_id, node_id, taught_at, source_type, source_id nullable, notes

## Exam assets
- exams: ... + exam_kind (school, mock, other)
- exam_files: id, exam_id, file_path, file_type (pdf/image), uploaded_at
- exam_answer_keys: exam_id, sequence_no, answer_key
- exam_attempts: id, exam_id, attempted_at, duration_minutes, notes
- exam_attempt_answers: attempt_id, sequence_no, user_answer, result

## Mock mapping
- exam_subject_sections: exam_id, subject_id, sequence_from, sequence_to
- exam_question_topic_map: exam_id, sequence_no, node_id

## Readiness
- upcoming_exams: id, title, exam_date, created_at
- upcoming_exam_topics: upcoming_exam_id, node_id
