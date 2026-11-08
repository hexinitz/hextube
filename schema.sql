CREATE TABLE IF NOT EXISTS videos (
  vid TEXT PRIMARY KEY CHECK(length(vid)=11),
  source TEXT NOT NULL CHECK(source IN ('hn','youtube')),
  score REAL NOT NULL DEFAULT 0,
  payload TEXT NOT NULL,
  added_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS videos_source_score ON videos(source, score DESC);
CREATE TABLE IF NOT EXISTS watched (
  vid TEXT PRIMARY KEY CHECK(length(vid)=11),
  watched_at INTEGER NOT NULL
);
