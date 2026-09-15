# Confidence & Evidence — V2.1

هر prediction یا ویژگی مهم باید داشته باشد:
- value
- confidence
- evidence_count
- last_updated

مثال:
```python
{
    "preferred_study_time": {
        "value": "09:00-11:00",
        "confidence": 0.82,
        "evidence_count": 30
    }
}
```

3 مشاهده نباید مثل 30 مشاهده اعتبار داشته باشد.

سیستم باید از overfitting رفتاری جلوگیری کند و در صورت کمبود داده از توصیه‌های محافظه‌کارانه استفاده کند.
