"""Admin contacts: a small platform CRM for leads and outreach.

The admin keeps a list of people who are not platform users yet - leads,
potential leads, partners - grouped by an editable category. Contacts are keyed
by email so a CSV import updates someone already known instead of duplicating
them, and deleting a category keeps its contacts (they become uncategorised).
"""
from __future__ import annotations

import csv
import io
import re
from uuid import UUID

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contact, ContactCategory

CATEGORY_COLORS = ("violet", "green", "yellow", "blue", "red", "neutral")
DEFAULT_COLOR = "violet"
MAX_IMPORT_ROWS = 20000
MAX_IMPORT_ERRORS = 20


class ContactConflict(ValueError):
    """The email or category name already exists."""


class ContactImportError(ValueError):
    """The uploaded file cannot be read as a contacts CSV."""


def normalize_email(value: str | None) -> str | None:
    """Lower-case and trim an address, or ``None`` when it is not valid."""
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    try:
        # check_deliverability=False keeps an import offline and fast; syntax is
        # what we need to reject obviously bad rows.
        return validate_email(cleaned, check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        return None


def normalize_color(value: str | None) -> str:
    color = (value or "").strip().lower()
    return color if color in CATEGORY_COLORS else DEFAULT_COLOR


def contact_payload(contact: Contact) -> dict:
    """Flatten a contact and its category for the API schema."""
    category = contact.category
    return {
        "id": contact.id,
        "email": contact.email,
        "name": contact.name,
        "phone": contact.phone,
        "company": contact.company,
        "category_id": contact.category_id,
        "category_name": category.name if category else None,
        "category_color": category.color if category else None,
        "source": contact.source,
        "notes": contact.notes,
        "created_at": contact.created_at,
        "updated_at": contact.updated_at,
    }


async def get_contact(db: AsyncSession, contact_id: UUID) -> Contact | None:
    return await db.scalar(select(Contact).where(Contact.id == contact_id))


async def contact_summary(db: AsyncSession) -> dict:
    """Total and per-category counts for the filter chips and category manager."""
    total = await db.scalar(select(func.count(Contact.id))) or 0
    uncategorized = await db.scalar(select(func.count(Contact.id)).where(Contact.category_id.is_(None))) or 0
    rows = (
        await db.execute(
            select(ContactCategory, func.count(Contact.id))
            .outerjoin(Contact, Contact.category_id == ContactCategory.id)
            .group_by(ContactCategory.id)
            .order_by(ContactCategory.name)
        )
    ).all()
    return {
        "total": total,
        "uncategorized": uncategorized,
        "categories": [
            {
                "id": category.id,
                "name": category.name,
                "color": category.color,
                "description": category.description,
                "contact_count": count,
            }
            for category, count in rows
        ],
    }


def _filters(search: str | None, category_id: UUID | None, uncategorized: bool) -> list:
    conditions = []
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                Contact.name.ilike(pattern),
                Contact.email.ilike(pattern),
                Contact.phone.ilike(pattern),
                Contact.company.ilike(pattern),
            )
        )
    if uncategorized:
        conditions.append(Contact.category_id.is_(None))
    elif category_id is not None:
        conditions.append(Contact.category_id == category_id)
    return conditions


async def list_contacts(
    db: AsyncSession,
    *,
    page: int = 1,
    limit: int = 50,
    search: str | None = None,
    category_id: UUID | None = None,
    uncategorized: bool = False,
) -> dict:
    """One page of contacts, newest first, with the full filtered total."""
    conditions = _filters(search, category_id, uncategorized)
    total = await db.scalar(select(func.count(Contact.id)).where(*conditions)) or 0
    pages = max(1, (total + limit - 1) // limit)
    current = min(max(page, 1), pages)
    rows = (
        await db.execute(
            select(Contact)
            .where(*conditions)
            .order_by(Contact.created_at.desc(), Contact.id.desc())
            .offset((current - 1) * limit)
            .limit(limit)
        )
    ).scalars().all()
    return {"items": [contact_payload(row) for row in rows], "total": total, "page": current, "page_size": limit, "pages": pages}


async def create_contact(
    db: AsyncSession,
    *,
    email: str,
    name: str | None = None,
    phone: str | None = None,
    company: str | None = None,
    category_id: UUID | None = None,
    source: str | None = None,
    notes: str | None = None,
) -> Contact:
    cleaned = normalize_email(email)
    if cleaned is None:
        raise ContactConflict("Enter a valid email address")
    if await db.scalar(select(Contact.id).where(Contact.email == cleaned)) is not None:
        raise ContactConflict("A contact with that email already exists")
    if category_id is not None and await db.get(ContactCategory, category_id) is None:
        raise ContactConflict("Category not found")
    contact = Contact(
        email=cleaned,
        name=(name or "").strip() or None,
        phone=(phone or "").strip() or None,
        company=(company or "").strip() or None,
        category_id=category_id,
        source=(source or "").strip() or None,
        notes=(notes or "").strip() or None,
    )
    db.add(contact)
    await db.flush()
    await db.refresh(contact)
    return contact


async def update_contact(db: AsyncSession, contact: Contact, values: dict) -> Contact:
    """Apply only the fields the caller supplied (``None`` clears a field)."""
    if "email" in values and values["email"] is not None:
        cleaned = normalize_email(values["email"])
        if cleaned is None:
            raise ContactConflict("Enter a valid email address")
        other = await db.scalar(select(Contact.id).where(Contact.email == cleaned, Contact.id != contact.id))
        if other is not None:
            raise ContactConflict("A contact with that email already exists")
        contact.email = cleaned
    if "category_id" in values:
        category_id = values["category_id"]
        if category_id is not None and await db.get(ContactCategory, category_id) is None:
            raise ContactConflict("Category not found")
        contact.category_id = category_id
    for field in ("name", "phone", "company", "source", "notes"):
        if field in values:
            value = values[field]
            setattr(contact, field, value.strip() or None if isinstance(value, str) else value)
    await db.flush()
    await db.refresh(contact)
    return contact


async def create_category(
    db: AsyncSession,
    *,
    name: str,
    color: str = DEFAULT_COLOR,
    description: str | None = None,
):
    cleaned = name.strip()
    if not cleaned:
        raise ContactConflict("Give the category a name")
    existing = await db.scalar(select(ContactCategory.id).where(func.lower(ContactCategory.name) == cleaned.lower()))
    if existing is not None:
        raise ContactConflict("A category with that name already exists")
    category = ContactCategory(name=cleaned, color=normalize_color(color), description=(description or "").strip() or None)
    db.add(category)
    await db.flush()
    await db.refresh(category)
    return category


async def update_category(
    db: AsyncSession,
    category: ContactCategory,
    *,
    name: str | None = None,
    color: str | None = None,
    description: str | None = None,
    update_description: bool = False,
):
    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            raise ContactConflict("Give the category a name")
        existing = await db.scalar(
            select(ContactCategory.id).where(
                func.lower(ContactCategory.name) == cleaned.lower(),
                ContactCategory.id != category.id,
            )
        )
        if existing is not None:
            raise ContactConflict("A category with that name already exists")
        category.name = cleaned
    if color is not None:
        category.color = normalize_color(color)
    if update_description:
        category.description = (description or "").strip() or None
    await db.flush()
    await db.refresh(category)
    return category


# ---------------------------------------------------------------------------
# CSV import
# ---------------------------------------------------------------------------

_HEADER_ALIASES = {
    "email": {"email", "e_mail", "mail", "email_address"},
    "name": {"name", "full_name", "contact", "contact_name", "first_name"},
    "phone": {"phone", "phone_number", "mobile", "tel", "telephone"},
    "company": {"company", "organization", "organisation", "business", "company_name"},
    "category": {"category", "type", "contact_type", "status"},
    "source": {"source", "origin"},
    "notes": {"notes", "note", "comments", "comment"},
}
_NORMALIZE_HEADER = re.compile(r"[^a-z0-9]+")


def _header_key(value: str) -> str:
    return _NORMALIZE_HEADER.sub("_", (value or "").strip().lstrip("\ufeff").lower()).strip("_")


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ContactImportError("The file is not valid text")


def _column_map(fieldnames: list[str] | None) -> dict[str, str]:
    if not fieldnames:
        raise ContactImportError("The CSV is empty")
    normalized = {_header_key(name): name for name in fieldnames if name}
    mapping: dict[str, str] = {}
    for field, aliases in _HEADER_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                mapping[field] = normalized[alias]
                break
    if "email" not in mapping:
        raise ContactImportError("The CSV needs an email column (e.g. email,name,phone,company,category)")
    return mapping


async def import_contacts(db: AsyncSession, raw: bytes, *, update_existing: bool = True) -> dict:
    """Create or update contacts from a CSV file.

    Columns are matched by common header aliases; unknown categories are created
    on the fly so an export from a spreadsheet is enough to start. Existing
    addresses are updated only when ``update_existing`` is true, and blank cells
    never erase a value.
    """
    text = _decode(raw)
    reader = csv.DictReader(io.StringIO(text))
    columns = _column_map(reader.fieldnames)

    parsed: list[dict] = []
    invalid = 0
    errors: list[str] = []
    for line_number, row in enumerate(reader, start=2):
        if line_number - 1 > MAX_IMPORT_ROWS:
            raise ContactImportError(f"Import at most {MAX_IMPORT_ROWS:,} contacts at a time")
        raw_email = (row.get(columns["email"]) or "").strip()
        if not raw_email and not any((value or "").strip() for value in row.values() if isinstance(value, str)):
            continue
        email = normalize_email(raw_email)
        if email is None:
            invalid += 1
            if len(errors) < MAX_IMPORT_ERRORS:
                errors.append(f"Line {line_number}: invalid email {raw_email or '(blank)'}")
            continue
        parsed.append(
            {
                "line": line_number,
                "email": email,
                "name": (row.get(columns.get("name", "")) or "").strip(),
                "phone": (row.get(columns.get("phone", "")) or "").strip(),
                "company": (row.get(columns.get("company", "")) or "").strip(),
                "category": (row.get(columns.get("category", "")) or "").strip(),
                "source": (row.get(columns.get("source", "")) or "csv").strip(),
                "notes": (row.get(columns.get("notes", "")) or "").strip(),
            }
        )

    emails = {item["email"] for item in parsed}
    existing_rows = (
        await db.execute(select(Contact).where(Contact.email.in_(emails)))
    ).scalars().all() if emails else []
    existing = {row.email: row for row in existing_rows}

    categories = {
        category.name.strip().lower(): category
        for category in (await db.execute(select(ContactCategory))).scalars().all()
    }
    categories_created = 0
    created = updated = skipped = 0

    for item in parsed:
        contact = existing.get(item["email"])
        category = None
        if item["category"]:
            key = item["category"].lower()
            category = categories.get(key)
            if category is None:
                category = ContactCategory(name=item["category"][:80], color=DEFAULT_COLOR)
                db.add(category)
                await db.flush()
                categories[key] = category
                categories_created += 1

        if contact is None:
            contact = Contact(
                email=item["email"],
                name=item["name"] or None,
                phone=item["phone"] or None,
                company=item["company"] or None,
                category_id=category.id if category else None,
                source=item["source"] or "csv",
                notes=item["notes"] or None,
            )
            db.add(contact)
            existing[item["email"]] = contact
            created += 1
            continue

        if not update_existing:
            skipped += 1
            continue
        if item["name"]:
            contact.name = item["name"]
        if item["phone"]:
            contact.phone = item["phone"]
        if item["company"]:
            contact.company = item["company"]
        if category is not None:
            contact.category_id = category.id
        if item["source"]:
            contact.source = item["source"]
        if item["notes"]:
            contact.notes = item["notes"]
        updated += 1

    await db.flush()
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "invalid": invalid,
        "categories_created": categories_created,
        "errors": errors,
    }
