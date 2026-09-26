from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Company, Membership, MembershipStore, Store, User
from app.security import decode_token


bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = decode_token(credentials.credentials)
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError, TypeError, jwt.PyJWTError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_current_membership(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Membership:
    result = await db.execute(
        select(Membership)
        .join(Company, Company.id == Membership.company_id)
        .where(Membership.user_id == user.id, Membership.status == "active", Company.is_active.is_(True))
        .order_by(Membership.created_at)
    )
    membership = result.scalars().first()
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Set up a workspace before using this feature")
    return membership


@dataclass
class StoreContext:
    user: User
    membership: Membership
    store: Store
    store_paused: bool = False


async def _resolve_store(db: AsyncSession, membership: Membership, store_id: UUID | None, *, active_only: bool) -> Store | None:
    """Resolve a store for a membership, optionally requiring it to be active."""
    if store_id:
        query = select(Store).where(Store.id == store_id, Store.company_id == membership.company_id)
        if active_only:
            query = query.where(Store.is_active.is_(True))
        if membership.role != "owner":
            query = query.join(MembershipStore, MembershipStore.store_id == Store.id).where(MembershipStore.membership_id == membership.id)
        return (await db.execute(query)).scalar_one_or_none()
    query = select(Store).where(Store.company_id == membership.company_id)
    if active_only:
        query = query.where(Store.is_active.is_(True))
    query = query.order_by(Store.created_at)
    if membership.role != "owner":
        query = query.join(MembershipStore, MembershipStore.store_id == Store.id).where(MembershipStore.membership_id == membership.id)
    return (await db.execute(query)).scalars().first()


async def get_store_context(
    user: User = Depends(get_current_user),
    membership: Membership = Depends(get_current_membership),
    store_id: UUID | None = Header(default=None, alias="X-Store-ID"),
    db: AsyncSession = Depends(get_db),
) -> StoreContext:
    """Resolve the active store for operational/write use.

    A paused (force-deactivated) store is refused with a clear message so the
    owner knows to upgrade; it is not the same as a missing store. Read-only
    history/report endpoints use ``get_store_context_read`` instead.
    """
    store = await _resolve_store(db, membership, store_id, active_only=True)
    if store is not None:
        return StoreContext(user=user, membership=membership, store=store)
    paused = await _resolve_store(db, membership, store_id, active_only=False)
    if paused is not None and not paused.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This store is paused or inactive. Reactivate it or upgrade your plan to continue.")
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found or not accessible")


async def get_store_context_read(
    user: User = Depends(get_current_user),
    membership: Membership = Depends(get_current_membership),
    store_id: UUID | None = Header(default=None, alias="X-Store-ID"),
    db: AsyncSession = Depends(get_db),
) -> StoreContext:
    """Resolve a store for read-only history/report use, paused stores included.

    A paused store cannot sell, but its data stays visible: history and reporting
    must not look like the store was deleted.
    """
    store = await _resolve_store(db, membership, store_id, active_only=False)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found or not accessible")
    return StoreContext(user=user, membership=membership, store=store, store_paused=not store.is_active)


def require_roles(*allowed_roles: str):
    async def dependency(membership: Membership = Depends(get_current_membership)) -> Membership:
        if membership.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your role cannot perform this action")
        return membership

    return dependency


async def get_platform_admin(user: User = Depends(get_current_user)) -> User:
    if user.platform_role not in {"admin", "super_admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform admin access required")
    return user


def require_super_admin(user: User = Depends(get_platform_admin)) -> User:
    if user.platform_role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin access required")
    return user
