from sqlalchemy import and_, exists, select

from efren_bot.collection.service import CollectionError
from efren_bot.human.models import HumanControl as H
from efren_bot.review.models import ReviewRequest as R


def identity(s, domain, row):
    if domain == "support":
        return {"domain": domain, "case_id": row.id}
    request = s.get(R, row.request_id)
    return {
        "domain": domain,
        "source_scope": request.source_scope,
        "project_path": row.project_path,
        "mr_iid": row.mr_iid,
    }


def control(s, domain, row):
    key = identity(s, domain, row)
    return s.scalar(select(H).where(*(getattr(H, k) == v for k, v in key.items())))


def epoch(s, domain, row):
    value = control(s, domain, row)
    return value.revision if value else 0


def active(s, domain, row):
    value = control(s, domain, row)
    return value is None or value.state == "active"


def require_active(s, domain, row):
    if not active(s, domain, row):
        raise CollectionError("human_control_required")


def blocked(domain, model):
    if domain == "support":
        return exists(
            select(H.id).where(H.domain == domain, H.case_id == model.id, H.state != "active")
        )
    return exists(
        select(H.id)
        .join(
            R,
            and_(
                H.source_scope == R.source_scope,
                H.project_path == model.project_path,
                H.mr_iid == model.mr_iid,
            ),
        )
        .where(H.domain == domain, H.state != "active", R.id == model.request_id)
    )
