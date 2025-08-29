from pydantic import BaseModel


class TelegramIdRequest(BaseModel):
    telegram_id: str

class GoToRequest(BaseModel):
    telegram_id: str
    target_scene_id: str

class SpendRequest(BaseModel):
    telegram_id: str
    amount: int