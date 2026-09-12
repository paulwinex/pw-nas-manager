from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.auth.dependencies import get_current_admin
from app.modules.groups import services
from app.modules.groups.schemas import (
    GroupCreate,
    GroupOut,
    LinkShare,
    MemberCreate,
    MemberOut,
)
from app.modules.shares.schemas import ShareOut

router = APIRouter(
    prefix="/groups",
    tags=["groups"],
    dependencies=[Depends(get_current_admin)],
)


@router.get("", response_model=list[GroupOut])
async def list_groups(session: AsyncSession = Depends(get_session)) -> list[GroupOut]:
    groups = await services.list_groups(session)
    return [GroupOut.model_validate(g) for g in groups]


@router.post("", response_model=GroupOut, status_code=201)
async def create_group(
    body: GroupCreate, session: AsyncSession = Depends(get_session)
) -> GroupOut:
    group = await services.create_group(session, body.name)
    return GroupOut.model_validate(group)


@router.delete("/{group_id}", status_code=204)
async def delete_group(group_id: str, session: AsyncSession = Depends(get_session)) -> None:
    await services.delete_group(session, group_id)


@router.get("/{group_id}/members", response_model=list[MemberOut])
async def list_members(
    group_id: str, session: AsyncSession = Depends(get_session)
) -> list[MemberOut]:
    members = await services.list_members(session, group_id)
    return [MemberOut.model_validate(m) for m in members]


@router.post("/{group_id}/members", response_model=MemberOut, status_code=201)
async def add_member(
    body: MemberCreate,
    group_id: str,
    session: AsyncSession = Depends(get_session),
) -> MemberOut:
    member = await services.add_member(session, group_id, body)
    return MemberOut.model_validate(member)


@router.delete("/{group_id}/members/{user_id}", status_code=204)
async def remove_member(
    group_id: str, user_id: str, session: AsyncSession = Depends(get_session)
) -> None:
    await services.remove_member(session, group_id, user_id)


@router.get("/{group_id}/shares", response_model=list[ShareOut])
async def list_group_shares(
    group_id: str, session: AsyncSession = Depends(get_session)
) -> list[ShareOut]:
    shares = await services.list_group_shares(session, group_id)
    return [ShareOut.model_validate(s) for s in shares]


@router.post("/{group_id}/shares", response_model=ShareOut, status_code=201)
async def link_share(
    body: LinkShare,
    group_id: str,
    session: AsyncSession = Depends(get_session),
) -> ShareOut:
    share = await services.link_share(session, group_id, body.share_id)
    return ShareOut.model_validate(share)


@router.delete("/{group_id}/shares/{share_id}", status_code=204)
async def unlink_share(
    group_id: str, share_id: str, session: AsyncSession = Depends(get_session)
) -> None:
    await services.unlink_share(session, group_id, share_id)