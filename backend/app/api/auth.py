from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import DB
from app.core.config import get_settings
from app.core.security import ROLES, create_access_token, get_current_user, hash_password, rate_limit, require_roles, verify_password
from app.models import Role, User
from app.schemas.assets import LoginIn, RegisterIn, TokenOut, UserCreate, UserOut, UserPatch
from app.services.common import audit

router = APIRouter(prefix="/api", tags=["auth"])
settings = get_settings()


@router.post("/auth/register", response_model=TokenOut, status_code=201, dependencies=[Depends(rate_limit)])
def register(body: RegisterIn, db: DB):
    if not settings.allow_self_register:
        raise HTTPException(403, "Self-registration is disabled")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(409, "Email already registered")
    u = User(email=body.email, full_name=body.full_name, hashed_password=hash_password(body.password), role=settings.default_register_role)
    db.add(u); db.commit()
    audit(db, u, "register", "user", u.id)
    return TokenOut(access_token=create_access_token(str(u.id), u.role), user=UserOut.model_validate(u))


@router.post("/auth/login", response_model=TokenOut, dependencies=[Depends(rate_limit)])
def login(body: LoginIn, db: DB):
    u = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if not u or not verify_password(body.password, u.hashed_password) or not u.is_active:
        raise HTTPException(401, "Invalid email or password")
    audit(db, u, "login", "user", u.id)
    return TokenOut(access_token=create_access_token(str(u.id), u.role), user=UserOut.model_validate(u))


@router.get("/auth/me", response_model=UserOut)
def me(user=Depends(get_current_user)):
    return user


@router.patch("/auth/me/preferences", response_model=UserOut)
def set_prefs(prefs: dict, db: DB, user=Depends(get_current_user)):
    if len(str(prefs)) > 4000:
        raise HTTPException(413, "Preferences too large")
    user.preferences = {**(user.preferences or {}), **prefs}
    db.commit()
    return user


@router.get("/roles")
def roles(user=Depends(get_current_user)):
    return [{"name": k, "description": v} for k, v in ROLES.items()]


@router.get("/users", response_model=list[UserOut])
def list_users(db: DB, user=Depends(get_current_user)):
    if user.role == "super_admin":
        return db.query(User).order_by(User.id).all()
    # other roles may list active users (needed for assignment dropdowns) but only basic data via UserOut
    return db.query(User).filter(User.is_active).order_by(User.full_name).all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: DB, admin=Depends(require_roles())):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(409, "Email already registered")
    u = User(email=body.email, full_name=body.full_name, hashed_password=hash_password(body.password), role=body.role, facility_id=body.facility_id)
    db.add(u); db.commit()
    audit(db, admin, "create_user", "user", u.id, {"role": u.role})
    return u


@router.patch("/users/{user_id}", response_model=UserOut)
def patch_user(user_id: int, body: UserPatch, db: DB, admin=Depends(require_roles())):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    data = body.model_dump(exclude_unset=True)
    if "password" in data:
        u.hashed_password = hash_password(data.pop("password"))
    if user_id == admin.id and (data.get("is_active") is False or (data.get("role") and data["role"] != "super_admin")):
        raise HTTPException(400, "You cannot deactivate or demote your own account")
    for k, v in data.items():
        setattr(u, k, v)
    db.commit()
    audit(db, admin, "update_user", "user", u.id, {k: v for k, v in data.items()})
    return u


def ensure_roles(db):
    for name, desc in ROLES.items():
        if not db.get(Role, name):
            db.add(Role(name=name, description=desc))
    db.commit()
