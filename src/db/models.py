from dataclasses import dataclass


@dataclass
class User:
    user_id: int
    created_at: str
    state: str
    is_banned: int
    rating: int
    chats_count: int
    interests: str
