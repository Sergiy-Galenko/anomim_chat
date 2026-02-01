CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    state TEXT NOT NULL,
    is_banned INTEGER NOT NULL DEFAULT 0,
    rating INTEGER NOT NULL DEFAULT 0,
    chats_count INTEGER NOT NULL DEFAULT 0,
    interests TEXT NOT NULL DEFAULT '',
    only_interest INTEGER NOT NULL DEFAULT 0,
    premium_until TEXT NOT NULL DEFAULT ''
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
    created_at TEXT NOT NULL
);
"""

SELECT_USER = "SELECT * FROM users WHERE user_id = ?"
INSERT_USER = """
INSERT OR IGNORE INTO users (user_id, created_at, state, is_banned, rating, chats_count)
VALUES (?, ?, ?, 0, 0, 0)
"""

UPDATE_STATE = "UPDATE users SET state = ? WHERE user_id = ?"
UPDATE_BANNED = "UPDATE users SET is_banned = ? WHERE user_id = ?"
INCREMENT_CHATS = "UPDATE users SET chats_count = chats_count + 1 WHERE user_id = ?"
UPDATE_INTERESTS = "UPDATE users SET interests = ? WHERE user_id = ?"
UPDATE_ONLY_INTEREST = "UPDATE users SET only_interest = ? WHERE user_id = ?"
UPDATE_PREMIUM_UNTIL = "UPDATE users SET premium_until = ? WHERE user_id = ?"

INSERT_QUEUE = "INSERT OR REPLACE INTO queue (user_id, joined_at) VALUES (?, ?)"
DELETE_QUEUE = "DELETE FROM queue WHERE user_id = ?"

SELECT_QUEUE_CANDIDATE = """
SELECT q.user_id
FROM queue q
JOIN users u ON u.user_id = q.user_id
WHERE q.user_id != ? AND u.state = 'searching' AND u.is_banned = 0
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
  AND u.interests = ?
ORDER BY q.joined_at ASC
LIMIT 1
"""

SELECT_QUEUE_CANDIDATES = """
SELECT q.user_id, u.interests, u.only_interest
FROM queue q
JOIN users u ON u.user_id = q.user_id
WHERE q.user_id != ? AND u.state = 'searching' AND u.is_banned = 0
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

STATS_USERS = "SELECT COUNT(*) AS count FROM users"
STATS_ACTIVE_CHATS = "SELECT COUNT(*) AS count FROM pairs WHERE is_active = 1"
STATS_QUEUE = "SELECT COUNT(*) AS count FROM queue"
STATS_REPORTS = "SELECT COUNT(*) AS count FROM reports"

SELECT_ACTIVE_USERS = """
SELECT user_id
FROM users
WHERE state IN ('searching', 'chatting') AND is_banned = 0
ORDER BY user_id ASC
"""

SELECT_INTERESTS = "SELECT interests FROM users WHERE user_id = ?"
SELECT_ONLY_INTEREST = "SELECT only_interest FROM users WHERE user_id = ?"
SELECT_PREMIUM_UNTIL = "SELECT premium_until FROM users WHERE user_id = ?"
