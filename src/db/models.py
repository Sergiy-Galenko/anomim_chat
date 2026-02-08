from dataclasses import dataclass


@dataclass
class User:
    user_id: int
    created_at: str
    state: str
    is_banned: int
    banned_until: str
    muted_until: str
    rating: int
    chats_count: int
    interests: str
    only_interest: int
    premium_until: str
    trial_used: int
    skip_until: str
    auto_search: int
    content_filter: int
    lang: str
