-- ユーザーテーブル（デモ用に簡略化）
CREATE TABLE users (
  id VARCHAR(50) PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- チャットルームテーブル
CREATE TABLE rooms (
  id VARCHAR(50) PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- メッセージテーブル
CREATE TABLE messages (
  id VARCHAR(50) PRIMARY KEY,
  room_id VARCHAR(50) NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
  user_id VARCHAR(50) NOT NULL REFERENCES users(id),
  text TEXT NOT NULL,
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 大規模時の検索高速化用インデックス（PostgreSQLではCREATE TABLE内にINDEX句を書けないため分離）
CREATE INDEX idx_room_timestamp ON messages (room_id, timestamp DESC);

-- ルームメンバーシップ（将来のユーザー管理向け）
CREATE TABLE room_members (
  room_id VARCHAR(50) NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
  user_id VARCHAR(50) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (room_id, user_id)
);

-- ダミーデータ：デモ用ユーザー
INSERT INTO users (id, name) VALUES
  ('user_a', 'User A'),
  ('user_b', 'User B'),
  ('user_c', 'User C');

-- ダミーデータ：デモ用ルーム
INSERT INTO rooms (id, name) VALUES
  ('room_general', '雑談ルーム'),
  ('room_dev', '開発相談ルーム');

-- ダミーデータ：初期メッセージ
INSERT INTO messages (id, room_id, user_id, text) VALUES
  ('msg_001', 'room_general', 'user_a', 'こんにちは！'),
  ('msg_002', 'room_general', 'user_b', 'よろしくお願いします'),
  ('msg_003', 'room_dev', 'user_c', 'WebSocketの実装から始めましょう');
