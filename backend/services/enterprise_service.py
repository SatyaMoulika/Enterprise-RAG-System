from sqlalchemy.orm import Session

from models.enterprise import Enterprise

from repositories.enterprise_repository import (
    EnterpriseRepository
)


class EnterpriseService:

    @staticmethod
    def create_enterprise(
        db: Session,
        name: str
    ):

        existing = (
            EnterpriseRepository.get_by_name(
                db=db,
                name=name
            )
        )

        if existing:
            raise ValueError(
                "Enterprise already exists"
            )

        enterprise = Enterprise(
            name=name
        )

        return (
            EnterpriseRepository.create(
                db=db,
                enterprise=enterprise
            )
        )