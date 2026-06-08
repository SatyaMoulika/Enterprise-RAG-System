from pydantic import BaseModel


class EnterpriseCreate(BaseModel):
    name: str


class EnterpriseResponse(BaseModel):
    id: int
    name: str
    is_active: bool
    
    class Config:
        from_attributes = True