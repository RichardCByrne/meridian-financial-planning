from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_plan_access
from app.db import get_db
from app.models import Person, Plan, User
from app.routers._helpers import get_or_404
from app.schemas.person import PersonCreate, PersonRead, PersonUpdate

router = APIRouter(tags=["people"])


@router.get("/plans/{plan_id}/people", response_model=list[PersonRead])
def list_people(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Person]:
    require_plan_access(plan_id, user, db, min_role="viewer")
    return list(
        db.execute(select(Person).where(Person.plan_id == plan_id).order_by(Person.id)).scalars()
    )


@router.post(
    "/plans/{plan_id}/people",
    response_model=PersonRead,
    status_code=status.HTTP_201_CREATED,
)
def create_person(
    plan_id: int,
    payload: PersonCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Person:
    require_plan_access(plan_id, user, db, min_role="editor")
    if db.get(Plan, plan_id) is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    person = Person(plan_id=plan_id, **payload.model_dump())
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


@router.patch("/people/{person_id}", response_model=PersonRead)
def update_person(
    person_id: int,
    payload: PersonUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Person:
    person = get_or_404(Person, person_id, db)
    require_plan_access(person.plan_id, user, db, min_role="editor")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(person, k, v)
    db.commit()
    db.refresh(person)
    return person


@router.delete("/people/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person(
    person_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    person = get_or_404(Person, person_id, db)
    require_plan_access(person.plan_id, user, db, min_role="editor")
    db.delete(person)
    db.commit()
