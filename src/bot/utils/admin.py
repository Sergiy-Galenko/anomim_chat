from ...config import Config


def is_admin(user_id: int, config: Config) -> bool:
    return user_id in config.admin_ids
