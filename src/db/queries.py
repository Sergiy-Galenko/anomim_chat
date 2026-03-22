CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    state TEXT NOT NULL,
    username TEXT NOT NULL DEFAULT '',
    first_name TEXT NOT NULL DEFAULT '',
    last_name TEXT NOT NULL DEFAULT '',
    last_seen_at TEXT NOT NULL DEFAULT '',
    is_banned INTEGER NOT NULL DEFAULT 0,
    banned_until TEXT NOT NULL DEFAULT '',
    muted_until TEXT NOT NULL DEFAULT '',
    rating INTEGER NOT NULL DEFAULT 0,
    chats_count INTEGER NOT NULL DEFAULT 0,
    interests TEXT NOT NULL DEFAULT '',
    only_interest INTEGER NOT NULL DEFAULT 0,
    premium_until TEXT NOT NULL DEFAULT '',
    trial_used INTEGER NOT NULL DEFAULT 0,
    skip_until TEXT NOT NULL DEFAULT '',
    auto_search INTEGER NOT NULL DEFAULT 0,
    content_filter INTEGER NOT NULL DEFAULT 1,
    lang TEXT NOT NULL DEFAULT 'ru'
);

CREATE TABLE IF NOT EXISTS pairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user1_id INTEGER NOT NULL,
    user2_id INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS queue (
    user_id INTEGER PRIMARY KEY,
    joined_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER NOT NULL,
    reported_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    resolved_at TEXT,
    resolved_by INTEGER
);

CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id INTEGER,
    target_id INTEGER,
    type TEXT NOT NULL,
    payload TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS promo_uses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    used_at TEXT NOT NULL,
    UNIQUE(user_id, code)
);

CREATE TABLE IF NOT EXISTS promo_codes (
    code TEXT PRIMARY KEY,
    days INTEGER NOT NULL,
    usage_limit INTEGER NOT NULL,
    used_count INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    created_by INTEGER
);

CREATE TABLE IF NOT EXISTS pending_ratings (
    user_id INTEGER PRIMARY KEY,
    pair_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pair_id INTEGER NOT NULL,
    rater_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    value INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(pair_id, rater_id)
);

CREATE TABLE IF NOT EXISTS media_archive (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER NOT NULL,
    receiver_id INTEGER NOT NULL,
    media_type TEXT NOT NULL,
    file_id TEXT NOT NULL,
    caption TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS virtual_dialog_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pair_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    companion_id INTEGER NOT NULL,
    speaker TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS virtual_ab_sessions (
    pair_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    companion_id INTEGER NOT NULL,
    variant_key TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL DEFAULT '',
    user_messages INTEGER NOT NULL DEFAULT 0,
    companion_messages INTEGER NOT NULL DEFAULT 0,
    media_messages INTEGER NOT NULL DEFAULT 0,
    ended_by_user INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS broadcasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audience TEXT NOT NULL,
    message TEXT NOT NULL,
    sent_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    created_by INTEGER,
    created_at TEXT NOT NULL
);
"""

SELECT_USER = "SELECT * FROM users WHERE user_id = ?"
INSERT_USER = """
INSERT OR IGNORE INTO users (user_id, created_at, state, is_banned, rating, chats_count)
VALUES (?, ?, ?, 0, 0, 0)
"""

UPSERT_USER_CONTEXT = """
INSERT INTO users (
    user_id,
    created_at,
    state,
    username,
    first_name,
    last_name,
    last_seen_at,
    is_banned,
    rating,
    chats_count
)
VALUES (?, ?, 'idle', ?, ?, ?, ?, 0, 0, 0)
ON CONFLICT(user_id) DO UPDATE SET
    username = excluded.username,
    first_name = excluded.first_name,
    last_name = excluded.last_name,
    last_seen_at = excluded.last_seen_at
"""

UPDATE_STATE = "UPDATE users SET state = ? WHERE user_id = ?"
UPDATE_USER_PROFILE = """
UPDATE users
SET username = ?, first_name = ?, last_name = ?, last_seen_at = ?
WHERE user_id = ?
"""
UPDATE_BANNED = "UPDATE users SET is_banned = ? WHERE user_id = ?"
UPDATE_BANNED_UNTIL = "UPDATE users SET banned_until = ? WHERE user_id = ?"
UPDATE_MUTED_UNTIL = "UPDATE users SET muted_until = ? WHERE user_id = ?"
INCREMENT_CHATS = "UPDATE users SET chats_count = chats_count + 1 WHERE user_id = ?"
INCREMENT_RATING = "UPDATE users SET rating = rating + ? WHERE user_id = ?"
UPDATE_INTERESTS = "UPDATE users SET interests = ? WHERE user_id = ?"
UPDATE_ONLY_INTEREST = "UPDATE users SET only_interest = ? WHERE user_id = ?"
UPDATE_PREMIUM_UNTIL = "UPDATE users SET premium_until = ? WHERE user_id = ?"
UPDATE_TRIAL_USED = "UPDATE users SET trial_used = ? WHERE user_id = ?"
UPDATE_SKIP_UNTIL = "UPDATE users SET skip_until = ? WHERE user_id = ?"
UPDATE_AUTO_SEARCH = "UPDATE users SET auto_search = ? WHERE user_id = ?"
UPDATE_CONTENT_FILTER = "UPDATE users SET content_filter = ? WHERE user_id = ?"
UPDATE_LANG = "UPDATE users SET lang = ? WHERE user_id = ?"

INSERT_QUEUE = "INSERT OR REPLACE INTO queue (user_id, joined_at) VALUES (?, ?)"
DELETE_QUEUE = "DELETE FROM queue WHERE user_id = ?"
SELECT_QUEUE_SIZE = "SELECT COUNT(*) AS count FROM queue"
SELECT_QUEUE_JOINED_AT = "SELECT joined_at FROM queue WHERE user_id = ?"
SELECT_QUEUE_POSITION = """
SELECT COUNT(*) + 1 AS pos
FROM queue
WHERE joined_at < (SELECT joined_at FROM queue WHERE user_id = ?)
"""

SELECT_QUEUE_CANDIDATE = """
SELECT q.user_id
FROM queue q
JOIN users u ON u.user_id = q.user_id
WHERE q.user_id != ?
  AND u.state = 'searching'
  AND u.is_banned = 0
  AND (u.banned_until = '' OR u.banned_until <= ?)
ORDER BY q.joined_at ASC
LIMIT 1
"""

SELECT_QUEUE_CANDIDATE_INTEREST = """
SELECT q.user_id
FROM queue q
JOIN users u ON u.user_id = q.user_id
WHERE q.user_id != ?
  AND u.state = 'searching'
  AND u.is_banned = 0
  AND (u.banned_until = '' OR u.banned_until <= ?)
  AND u.interests = ?
ORDER BY q.joined_at ASC
LIMIT 1
"""

SELECT_QUEUE_CANDIDATES = """
SELECT q.user_id, q.joined_at, u.interests, u.only_interest, u.premium_until
FROM queue q
JOIN users u ON u.user_id = q.user_id
WHERE q.user_id != ?
  AND u.state = 'searching'
  AND u.is_banned = 0
  AND (u.banned_until = '' OR u.banned_until <= ?)
ORDER BY q.joined_at ASC
"""
INSERT_PAIR = """
INSERT INTO pairs (user1_id, user2_id, started_at, ended_at, is_active)
VALUES (?, ?, ?, NULL, 1)
"""

SELECT_ACTIVE_PAIR = """
SELECT * FROM pairs
WHERE is_active = 1 AND (user1_id = ? OR user2_id = ?)
LIMIT 1
"""

END_PAIR_BY_ID = """
UPDATE pairs SET ended_at = ?, is_active = 0 WHERE id = ?
"""

INSERT_REPORT = """
INSERT INTO reports (reporter_id, reported_id, reason, created_at)
VALUES (?, ?, ?, ?)
"""

SELECT_NEXT_REPORT = """
SELECT * FROM reports
WHERE status = 'new'
ORDER BY created_at ASC
LIMIT 1
"""

SELECT_REPORT_BY_ID = "SELECT * FROM reports WHERE id = ?"

UPDATE_REPORT_STATUS = """
UPDATE reports
SET status = ?, resolved_at = ?, resolved_by = ?
WHERE id = ?
"""

INSERT_INCIDENT = """
INSERT INTO incidents (actor_id, target_id, type, payload, created_at)
VALUES (?, ?, ?, ?, ?)
"""

INSERT_PROMO_USE = """
INSERT INTO promo_uses (user_id, code, used_at)
VALUES (?, ?, ?)
"""

INSERT_PROMO_CODE = """
INSERT INTO promo_codes (code, days, usage_limit, used_count, is_active, created_at, created_by)
VALUES (?, ?, ?, 0, 1, ?, ?)
"""

SELECT_PROMO_CODE = """
SELECT code, days, usage_limit, used_count, is_active, created_at, created_by
FROM promo_codes
WHERE code = ?
LIMIT 1
"""

SELECT_RECENT_PROMO_CODES = """
SELECT code, days, usage_limit, used_count, is_active, created_at, created_by
FROM promo_codes
ORDER BY created_at DESC
LIMIT ?
"""

UPDATE_PROMO_CODE_USAGE = """
UPDATE promo_codes
SET used_count = used_count + 1
WHERE code = ?
"""

UPSERT_APP_SETTING = """
INSERT INTO app_settings (key, value)
VALUES (?, ?)
ON CONFLICT(key) DO UPDATE SET value = excluded.value
"""

SELECT_APP_SETTING = """
SELECT value
FROM app_settings
WHERE key = ?
LIMIT 1
"""

INSERT_PENDING_RATING = """
INSERT OR REPLACE INTO pending_ratings (user_id, pair_id, target_id, created_at)
VALUES (?, ?, ?, ?)
"""

SELECT_PENDING_RATING = """
SELECT pair_id, target_id
FROM pending_ratings
WHERE user_id = ?
"""

DELETE_PENDING_RATING = "DELETE FROM pending_ratings WHERE user_id = ?"

INSERT_CHAT_FEEDBACK = """
INSERT INTO chat_feedback (pair_id, rater_id, target_id, value, created_at)
VALUES (?, ?, ?, ?, ?)
"""

INSERT_MEDIA_ARCHIVE = """
INSERT INTO media_archive (sender_id, receiver_id, media_type, file_id, caption, created_at)
VALUES (?, ?, ?, ?, ?, ?)
"""

INSERT_VIRTUAL_DIALOG_MEMORY = """
INSERT INTO virtual_dialog_memory (pair_id, user_id, companion_id, speaker, content, created_at)
VALUES (?, ?, ?, ?, ?, ?)
"""

INSERT_VIRTUAL_AB_SESSION = """
INSERT OR REPLACE INTO virtual_ab_sessions (
    pair_id,
    user_id,
    companion_id,
    variant_key,
    started_at,
    ended_at,
    user_messages,
    companion_messages,
    media_messages,
    ended_by_user
)
VALUES (?, ?, ?, ?, ?, '', 0, 0, 0, 0)
"""

SELECT_VIRTUAL_AB_SESSION = """
SELECT pair_id, user_id, companion_id, variant_key, started_at, ended_at,
       user_messages, companion_messages, media_messages, ended_by_user
FROM virtual_ab_sessions
WHERE pair_id = ?
LIMIT 1
"""

INCREMENT_VIRTUAL_AB_USER_MESSAGE = """
UPDATE virtual_ab_sessions
SET user_messages = user_messages + 1,
    media_messages = media_messages + ?
WHERE pair_id = ?
"""

INCREMENT_VIRTUAL_AB_COMPANION_MESSAGE = """
UPDATE virtual_ab_sessions
SET companion_messages = companion_messages + 1
WHERE pair_id = ?
"""

FINISH_VIRTUAL_AB_SESSION = """
UPDATE virtual_ab_sessions
SET ended_at = ?,
    ended_by_user = CASE WHEN ? = 1 THEN 1 ELSE ended_by_user END
WHERE pair_id = ?
"""

SELECT_ALL_VIRTUAL_AB_SESSIONS = """
SELECT pair_id, user_id, companion_id, variant_key, started_at, ended_at,
       user_messages, companion_messages, media_messages, ended_by_user
FROM virtual_ab_sessions
ORDER BY started_at DESC
"""

SELECT_VIRTUAL_DIALOG_MEMORY = """
SELECT speaker, content, created_at
FROM virtual_dialog_memory
WHERE pair_id = ?
ORDER BY id DESC
LIMIT ?
"""

DELETE_OLD_VIRTUAL_DIALOG_MEMORY = """
DELETE FROM virtual_dialog_memory
WHERE pair_id = ?
  AND id NOT IN (
    SELECT id
    FROM virtual_dialog_memory
    WHERE pair_id = ?
    ORDER BY id DESC
    LIMIT ?
  )
"""

DELETE_OLD_MEDIA_ARCHIVE = """
DELETE FROM media_archive
WHERE created_at < ?
"""

COUNT_RECENT_MEDIA_ARCHIVE = """
SELECT COUNT(*) AS count
FROM media_archive
WHERE created_at >= ?
"""

SELECT_RECENT_MEDIA_ARCHIVE = """
SELECT id, sender_id, receiver_id, media_type, file_id, caption, created_at
FROM media_archive
WHERE created_at >= ?
ORDER BY created_at DESC
LIMIT ? OFFSET ?
"""

SELECT_MEDIA_ARCHIVE_BY_ID = """
SELECT id, sender_id, receiver_id, media_type, file_id, caption, created_at
FROM media_archive
WHERE id = ?
LIMIT 1
"""

DELETE_MEDIA_ARCHIVE_BY_ID = """
DELETE FROM media_archive
WHERE id = ?
"""

SELECT_CHAT_FEEDBACK_EXISTS = """
SELECT id
FROM chat_feedback
WHERE pair_id = ? AND rater_id = ?
"""

SELECT_PROMO_USE = """
SELECT id FROM promo_uses WHERE user_id = ? AND code = ?
"""

STATS_USERS = "SELECT COUNT(*) AS count FROM users"
STATS_ACTIVE_CHATS = "SELECT COUNT(*) AS count FROM pairs WHERE is_active = 1"
STATS_QUEUE = "SELECT COUNT(*) AS count FROM queue"
STATS_REPORTS = "SELECT COUNT(*) AS count FROM reports"
STATS_BANNED = "SELECT COUNT(*) AS count FROM users WHERE is_banned = 1"
STATS_TEMP_BANNED = """
SELECT COUNT(*) AS count
FROM users
WHERE is_banned = 0 AND banned_until != '' AND banned_until > ?
"""

COUNT_USERS_CREATED_SINCE = """
SELECT COUNT(*) AS count
FROM users
WHERE created_at >= ?
"""

COUNT_USERS_SEEN_SINCE = """
SELECT COUNT(*) AS count
FROM users
WHERE last_seen_at >= ?
"""

COUNT_USERS_WITH_CHATS = """
SELECT COUNT(*) AS count
FROM users
WHERE chats_count > 0
"""

COUNT_PREMIUM_ACTIVE = """
SELECT COUNT(*) AS count
FROM users
WHERE premium_until != '' AND premium_until > ?
"""

COUNT_PREMIUM_BUYERS = """
SELECT COUNT(DISTINCT actor_id) AS count
FROM incidents
WHERE type = 'payment' AND actor_id IS NOT NULL
"""

COUNT_PAYMENT_INCIDENTS = """
SELECT COUNT(*) AS count
FROM incidents
WHERE type = 'payment'
"""

COUNT_PROMO_USERS = """
SELECT COUNT(DISTINCT user_id) AS count
FROM promo_uses
"""

COUNT_PROMO_CODES = """
SELECT COUNT(*) AS count
FROM promo_codes
"""

COUNT_VIRTUAL_CHAT_USERS = """
SELECT COUNT(DISTINCT CASE
    WHEN user1_id < 0 THEN user2_id
    ELSE user1_id
END) AS count
FROM pairs
WHERE user1_id < 0 OR user2_id < 0
"""

COUNT_ACTIVE_VIRTUAL_CHATS = """
SELECT COUNT(*) AS count
FROM pairs
WHERE is_active = 1 AND (user1_id < 0 OR user2_id < 0)
"""

COUNT_VIRTUAL_CHATS_FOR_USER = """
SELECT COUNT(*) AS count
FROM pairs
WHERE (user1_id = ? AND user2_id < 0) OR (user2_id = ? AND user1_id < 0)
"""

SELECT_PAYMENT_INCIDENTS = """
SELECT actor_id, payload, created_at
FROM incidents
WHERE type = 'payment'
ORDER BY created_at DESC
"""

INSERT_BROADCAST = """
INSERT INTO broadcasts (audience, message, sent_count, failed_count, created_by, created_at)
VALUES (?, ?, ?, ?, ?, ?)
"""

SELECT_RECENT_BROADCASTS = """
SELECT id, audience, message, sent_count, failed_count, created_by, created_at
FROM broadcasts
ORDER BY created_at DESC
LIMIT ?
"""

SELECT_ACTIVE_USERS = """
SELECT user_id
FROM users
WHERE state IN ('searching', 'chatting')
  AND is_banned = 0
  AND (banned_until = '' OR banned_until <= ?)
ORDER BY user_id ASC
"""

SELECT_ALL_USERS = """
SELECT *
FROM users
ORDER BY created_at DESC
"""

SELECT_BROADCAST_ALL_USER_IDS = """
SELECT user_id
FROM users
WHERE is_banned = 0
  AND (banned_until = '' OR banned_until <= ?)
ORDER BY user_id ASC
"""

SELECT_BROADCAST_NON_PREMIUM_USER_IDS = """
SELECT user_id
FROM users
WHERE is_banned = 0
  AND (banned_until = '' OR banned_until <= ?)
  AND (premium_until = '' OR premium_until <= ?)
ORDER BY user_id ASC
"""

SELECT_BROADCAST_INACTIVE_USER_IDS = """
SELECT user_id
FROM users
WHERE is_banned = 0
  AND (banned_until = '' OR banned_until <= ?)
  AND (last_seen_at = '' OR last_seen_at < ?)
ORDER BY user_id ASC
"""

SEARCH_USERS = """
SELECT *
FROM users
WHERE CAST(user_id AS TEXT) = ?
   OR LOWER(username) = LOWER(?)
   OR LOWER(username) LIKE LOWER(?)
   OR LOWER(first_name) LIKE LOWER(?)
   OR LOWER(last_name) LIKE LOWER(?)
   OR LOWER(TRIM(first_name || ' ' || last_name)) LIKE LOWER(?)
ORDER BY
    CASE
        WHEN CAST(user_id AS TEXT) = ? THEN 0
        WHEN LOWER(username) = LOWER(?) THEN 1
        ELSE 2
    END,
    last_seen_at DESC,
    created_at DESC
LIMIT ?
"""

SELECT_RECENT_INCIDENTS_FOR_USER = """
SELECT id, actor_id, target_id, type, payload, created_at
FROM incidents
WHERE actor_id = ? OR target_id = ?
ORDER BY created_at DESC
LIMIT ?
"""

COUNT_INCIDENTS_FOR_USER = """
SELECT COUNT(*) AS count
FROM incidents
WHERE actor_id = ? OR target_id = ?
"""

SELECT_PARTNER_HISTORY = """
SELECT DISTINCT
    CASE
        WHEN user1_id = ? THEN user2_id
        ELSE user1_id
    END AS partner_id
FROM pairs
WHERE user1_id = ? OR user2_id = ?
"""

SELECT_INTERESTS = "SELECT interests FROM users WHERE user_id = ?"
SELECT_ONLY_INTEREST = "SELECT only_interest FROM users WHERE user_id = ?"
SELECT_PREMIUM_UNTIL = "SELECT premium_until FROM users WHERE user_id = ?"
SELECT_TRIAL_USED = "SELECT trial_used FROM users WHERE user_id = ?"
SELECT_SKIP_UNTIL = "SELECT skip_until FROM users WHERE user_id = ?"
SELECT_BANNED_UNTIL = "SELECT banned_until FROM users WHERE user_id = ?"
SELECT_MUTED_UNTIL = "SELECT muted_until FROM users WHERE user_id = ?"
SELECT_AUTO_SEARCH = "SELECT auto_search FROM users WHERE user_id = ?"
SELECT_CONTENT_FILTER = "SELECT content_filter FROM users WHERE user_id = ?"
SELECT_LANG = "SELECT lang FROM users WHERE user_id = ?"
SELECT_ALL_PREMIUM_UNTIL = "SELECT premium_until FROM users"
