from pydantic_settings import BaseSettings
from typing import Optional, List
import os

class Settings(BaseSettings):
    app_name: str = "StudyS459"
    env: str = "development"
    secret_key: str = "dev-secret-key-change-in-prod-32chars-long"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    database_url: str = "sqlite:///./studys459.db"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    
    # Open decisions - configurable
    mastery_correct_weight: float = 1.0
    mastery_wrong_penalty: float = 0.3
    mastery_decay_days: int = 30
    mastery_min_attempts_for_mastery: int = 3
    
    scoring_formula: str = "standard"  # standard, negative_marking, etc
    difficulty_weighting_enabled: bool = True
    difficulty_weights: str = "1:1.0,2:1.2,3:1.5"  # level:weight
    
    spaced_repetition_strategy: str = "simple"  # simple, sm2, configurable
    review_interval_days: str = "1,3,7,14,30"
    
    recent_question_exclusion_days: int = 7
    exam_influence_on_mastery: float = 0.5
    
    telegram_bot_token: Optional[str] = None
    telegram_webhook_secret: Optional[str] = None
    telegram_report_times: str = "08:00,20:00"  # configurable
    
    timezone_default: str = "Asia/Tehran"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def get_difficulty_weights(self) -> dict:
        result = {}
        for pair in self.difficulty_weights.split(","):
            if ":" in pair:
                k, v = pair.split(":")
                try:
                    result[int(k.strip())] = float(v.strip())
                except:
                    continue
        return result or {1:1.0,2:1.2,3:1.5}
    
    def get_review_intervals(self) -> List[int]:
        try:
            return [int(x.strip()) for x in self.review_interval_days.split(",")]
        except:
            return [1,3,7,14,30]

settings = Settings()
