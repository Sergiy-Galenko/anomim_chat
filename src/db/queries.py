CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    state TEXT NOT NULL,
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
"""

SELECT_USER = "SELECT * FROM users WHERE user_id = ?"
INSERT_USER = """
INSERT OR IGNORE INTO users (user_id, created_at, state, is_banned, rating, chats_count)
VALUES (?, ?, ?, 0, 0, 0)
"""

UPDATE_STATE = "UPDATE users SET state = ? WHERE user_id = ?"
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

SELECT_ACTIVE_USERS = """
SELECT user_id
FROM users
WHERE state IN ('searching', 'chatting')
  AND is_banned = 0
  AND (banned_until = '' OR banned_until <= ?)
ORDER BY user_id ASC
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
