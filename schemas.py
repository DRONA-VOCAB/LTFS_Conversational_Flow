from pydantic import BaseModel

class IdentityRequest(BaseModel):
    customer_name: str


class BotResponse(BaseModel):
    message: str
    verified: bool | None = None
    customer_id: int | None = None
